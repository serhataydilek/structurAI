# RealityScan automation status

RealityScan executable discovery works through `REALITYSCAN_EXE`, PATH, and common Epic install locations. The supported local configuration is the Windows user environment variable:

```text
REALITYSCAN_EXE=C:\Program Files\Epic Games\RealityScan_2.1\RealityScan.exe
```

The current local executable is:

```text
C:\Program Files\Epic Games\RealityScan_2.1\RealityScan.exe
```

Structura can safely probe the executable for version/help output. Full headless command automation is not enabled yet because this RealityScan version's command syntax has not been verified.

Current recommended workflow:

1. Prepare a RealityScan job in Structura.
2. Open RealityScan manually.
3. Import the prepared job input folder.
4. Align images, reconstruct the model, and build texture.
5. Export OBJ + MTL + textures as one ZIP.
6. Import the ZIP into Model Artifacts.
