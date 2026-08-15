const encoder = new TextEncoder();

function json(body, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json", "cache-control": "no-store" },
  });
}

function base64url(value) {
  const bytes = value instanceof Uint8Array ? value : encoder.encode(value);
  let binary = "";
  for (const byte of bytes) binary += String.fromCharCode(byte);
  return btoa(binary).replace(/=/g, "").replace(/\+/g, "-").replace(/\//g, "_");
}

async function sha256(value) {
  return base64url(new Uint8Array(await crypto.subtle.digest("SHA-256", encoder.encode(value))));
}

function pemToBytes(pem) {
  const raw = pem.replace(/-----[^-]+-----/g, "").replace(/\s/g, "");
  return Uint8Array.from(atob(raw), (c) => c.charCodeAt(0));
}

let cachedJwt;
async function apnsJwt(env) {
  const now = Math.floor(Date.now() / 1000);
  if (cachedJwt && now - cachedJwt.iat < 45 * 60) return cachedJwt.token;
  const header = base64url(JSON.stringify({ alg: "ES256", kid: env.APNS_KEY_ID }));
  const payload = base64url(JSON.stringify({ iss: env.APNS_TEAM_ID, iat: now }));
  const input = `${header}.${payload}`;
  const key = await crypto.subtle.importKey("pkcs8", pemToBytes(env.APNS_PRIVATE_KEY), { name: "ECDSA", namedCurve: "P-256" }, false, ["sign"]);
  const signature = new Uint8Array(await crypto.subtle.sign({ name: "ECDSA", hash: "SHA-256" }, key, encoder.encode(input)));
  const token = `${input}.${base64url(signature)}`;
  cachedJwt = { iat: now, token };
  return token;
}

function cleanToken(value) {
  return String(value || "").replace(/[^a-fA-F0-9]/g, "").toLowerCase();
}

async function register(request, env) {
  const body = await request.json();
  const apnsToken = cleanToken(body.apnsToken);
  const bundleId = String(body.bundleId || "").trim();
  const installationId = String(body.installationId || "").trim();
  if (apnsToken.length < 32 || !bundleId || !installationId) return json({ ok: false, reason: "Invalid registration" }, 400);
  const relayHandle = `cvz_${crypto.randomUUID()}`;
  const sendGrant = base64url(crypto.getRandomValues(new Uint8Array(32)));
  await env.REGISTRATIONS.put(relayHandle, JSON.stringify({
    apnsToken, bundleId, installationId,
    environment: body.environment === "sandbox" ? "sandbox" : "production",
    grantHash: await sha256(sendGrant), createdAt: new Date().toISOString(),
  }), { expirationTtl: 15552000 });
  return json({ ok: true, relayHandle, sendGrant, expiresIn: 15552000 });
}

async function send(request, env) {
  const grant = String(request.headers.get("authorization") || "").replace(/^Bearer\s+/i, "").trim();
  const body = await request.json();
  const relayHandle = String(body.relayHandle || "").trim();
  const record = JSON.parse((await env.REGISTRATIONS.get(relayHandle)) || "null");
  if (!record || !grant || (await sha256(grant)) !== record.grantHash) return json({ ok: false, reason: "Invalid relay grant" }, 401);
  const authority = record.environment === "sandbox" ? "https://api.sandbox.push.apple.com" : "https://api.push.apple.com";
  const payload = { aps: { alert: { title: String(body.title || "Ceviz"), body: String(body.message || "Görev tamamlandı.") }, sound: "default", "thread-id": "ceviz-jobs" }, job_id: String(body.jobId || ""), deep_link: String(body.deepLink || "") };
  const response = await fetch(`${authority}/3/device/${record.apnsToken}`, { method: "POST", headers: { authorization: `bearer ${await apnsJwt(env)}`, "apns-topic": record.bundleId, "apns-push-type": "alert", "apns-priority": "10", "content-type": "application/json" }, body: JSON.stringify(payload) });
  const reason = await response.text();
  if (!response.ok && [400, 410].includes(response.status)) await env.REGISTRATIONS.delete(relayHandle);
  return json({ ok: response.ok, status: response.status, apnsId: response.headers.get("apns-id") || "", reason }, response.ok ? 200 : 502);
}

export default {
  async fetch(request, env) {
    const path = new URL(request.url).pathname;
    try {
      if (request.method === "GET" && path === "/healthz") return json({ ok: true });
      if (request.method === "POST" && path === "/v1/register") return await register(request, env);
      if (request.method === "POST" && path === "/v1/send") return await send(request, env);
      return json({ ok: false, reason: "Not found" }, 404);
    } catch (error) { return json({ ok: false, reason: error?.message || String(error) }, 500); }
  },
};
