#!/usr/bin/env bash
set -e

echo "=> Building standalone binary with PyInstaller..."
uv pip install pyinstaller
uv run pyinstaller packaging/shotx.spec --distpath dist --workpath build

echo "=> Preparing AppDir structure..."
rm -rf AppDir
mkdir -p AppDir/usr/bin AppDir/usr/share/applications AppDir/usr/share/icons/hicolor/scalable/apps

echo "=> Copying binary and assets..."
cp dist/shotx AppDir/usr/bin/shotx
cp packaging/shotx.desktop AppDir/usr/share/applications/io.github.vedeshpadal.ShotX.desktop
cp packaging/shotx.desktop AppDir/shotx.desktop
cp src/shotx/assets/shotx.svg AppDir/usr/share/icons/hicolor/scalable/apps/io.github.vedeshpadal.ShotX.svg
cp src/shotx/assets/shotx.svg AppDir/shotx.svg

echo "=> Creating execution link..."
ln -s usr/bin/shotx AppDir/AppRun

echo "=> Downloading appimagetool..."
if [ ! -f "appimagetool" ]; then
    wget -qO appimagetool https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage
    chmod +x appimagetool
fi

echo "=> Building final AppImage..."
# Using --appimage-extract-and-run to ensure it works properly even if local FUSE support is missing
./appimagetool --appimage-extract-and-run AppDir dist/ShotX-local-x86_64.AppImage

echo "=> Cleaning up temporary AppDir..."
rm -rf AppDir

echo "=========================================================="
echo "=> Done! Your local AppImage is natively built and ready:"
echo "=> ./dist/ShotX-local-x86_64.AppImage"
echo "=========================================================="
