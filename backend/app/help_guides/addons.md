# Add-ons on dedicated servers

- Prefer packs with both **behavior (BP)** and **resource (RP)** halves. MineForge flags missing pairs.
- **Marketplace / encrypted** packs cannot load on a dedicated server — they are detected and skipped.
- Packs that need **Beta APIs / experiments** require experiments enabled in the world (`level.dat`) before import; the server cannot toggle that remotely.
- World-embedded packs from imports are preserved when applying a profile.
- Large packs slow phone joins; check download size on the Add-ons per-world tab.

Some client UIs fail to render add-on dialog buttons — that is a client issue and cannot be fixed server-side.
