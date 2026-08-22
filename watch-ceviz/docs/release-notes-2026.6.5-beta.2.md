# Ceviz 2026.6.5 Beta 2

Beta 2 fixes the notification-to-result handoff on Apple Watch and moves the
validated build into the public TestFlight group.

## Fixed

- Tapping a terminal notification on Apple Watch now applies the authoritative
  terminal payload even if the corresponding pending poll record has already
  expired or been cleared.
- The Watch Home screen no longer remains on “result is being prepared” while
  the same job is already shown as complete in Jobs.

## Distribution and validation

- TestFlight build: **2026.6.5 (1787435232)**.
- **34/34** backend and contract tests passed; the iOS Release build, embedded
  watchOS app, signing, and TestFlight upload passed the same required CI gate
  in [workflow run 32600537529](https://github.com/MertBasar0/openclaw/actions/runs/32600537529).
- The notification fix was confirmed by the user on a physical iPhone and
  Apple Watch: the notification arrived without opening Ceviz, tapping it
  opened the completed result, and Home reflected the terminal state.
- The build was assigned to the external public **Beta** group and read back as
  **VALID / BETA_APPROVED** in
  [workflow run 32605320929](https://github.com/MertBasar0/openclaw/actions/runs/32605320929).

## Open-beta validation scope

- Clean technical onboarding was validated in an isolated Ubuntu 24.04 WSL2
  environment, including install, service startup, QR pairing, authenticated
  relay access, command polling, and restart persistence.
- Independent unassisted onboarding was not performed because suitable extra
  devices and testers were unavailable. This is an accepted open-beta risk,
  not a passed test; the first real external installs will be monitored.
- macOS and bare Linux remain feedback targets. WSL2 is currently the most
  thoroughly validated installation path.

## Known limitations

- The first command may take a few minutes while Whisper downloads its model.
- Short, focused voice commands work best within watchOS recording limits.
- Tailscale users should enable VPN On Demand so background iOS/watchOS access
  can continue across networks.

## Links

- [Join the open beta on TestFlight](https://testflight.apple.com/join/nEdn2Np2)
- [Product and setup overview](https://basarlabs.com.tr/ceviz/)
- [Privacy policy](https://basarlabs.com.tr/ceviz/privacy/)
