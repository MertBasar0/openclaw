# Ceviz 2026.6.5 Beta 1

Ceviz turns Apple Watch and iPhone into a compact control surface for
developers and operators who run OpenClaw on their own machine.

## Highlights

- Send a short voice command from Apple Watch, read the result summary on your
  wrist, and open the detailed report on iPhone.
- Keep follow-up commands in the same conversation, navigate job chains, and
  see subagents, tools, and actionable next steps.
- Install the self-hosted backend with one command, pair by QR code, and choose
  Tailscale or the built-in Windows relay for WSL2.
- Explore every core screen without an account or backend through the automatic
  Demo Mode on a fresh install.
- Use English as the base language or the complete Turkish localization.
- Receive terminal job notifications on iPhone and Apple Watch, with a distinct
  completion sound and recovery after device sleep or app relaunch.

## Security and privacy

- Commands go only to the self-hosted backend configured by the user.
- Backend access uses a bearer token stored in the iOS Keychain.
- Plain HTTP is accepted only for local-network relay addresses; public
  endpoints require HTTPS.
- Speech is transcribed by Whisper on the user's machine by default. The app
  includes no analytics, advertising, or tracking SDKs.

## Validation

- **34/34** backend and contract tests passed.
- The iOS Release build, embedded watchOS app, and TestFlight upload passed the
  same required CI gate.
- TestFlight build: **2026.6.5 (1787259702)**.
- A physical iPhone + Apple Watch smoke test passed for direct Watch push,
  result presentation, and the notification sound.
- A clean Ubuntu 24.04 WSL2 onboarding verified install, QR pairing, 401/200
  authentication, command polling, and service persistence after restart.
- App Store-sized simulator screenshots were generated and validated by the
  [screenshot workflow](https://github.com/MertBasar0/openclaw/actions/workflows/ceviz-screenshots.yml).

## Known limitations

- The first command may take a few minutes while Whisper downloads its model.
- Short, focused voice commands work best within watchOS recording limits.
- WSL2 received the most complete installation validation; macOS and bare Linux
  still need more external-user feedback.
- Independent, unassisted onboarding remains an open-beta usability check.

## Links

- [Join the open beta on TestFlight](https://testflight.apple.com/join/nEdn2Np2)
- [Product and setup overview](https://basarlabs.com.tr/ceviz/)
- [Privacy policy](https://basarlabs.com.tr/ceviz/privacy/)
