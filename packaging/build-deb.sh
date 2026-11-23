#!/bin/sh
set -eu
project=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
output=${1:-.}
stage=$(mktemp -d)
trap 'rm -rf -- "$stage"' EXIT
chmod 755 "$stage"
install -Dm644 "$project/packaging/control" "$stage/DEBIAN/control"
install -Dm644 "$project/packaging/jatayu-pdf-studio.desktop" \
    "$stage/usr/share/applications/jatayu-pdf-studio.desktop"
install -Dm644 "$project/packaging/copyright" "$stage/usr/share/doc/jatayu-pdf-studio/copyright"
app="$stage/usr/share/jatayu-pdf-studio"
install -d "$app/artwork" "$stage/usr/bin"
install -m644 "$project"/*.py "$app/"
install -m644 "$project"/artwork/*.png "$app/artwork/"
for size in 24 48 128 512; do
    install -Dm644 "$app/artwork/jatayu-pdf-studio-$size.png" \
        "$stage/usr/share/icons/hicolor/${size}x${size}/apps/jatayu-pdf-studio.png"
done
cat > "$stage/usr/bin/jatayu-pdf-studio" <<'LAUNCH'
#!/bin/sh
exec /usr/bin/python3 -I -c 'import runpy, sys; sys.path.insert(0, "/usr/share/jatayu-pdf-studio"); runpy.run_module("app", run_name="__main__")' "$@"
LAUNCH
chmod 755 "$stage/usr/bin/jatayu-pdf-studio"
version=$(sed -n 's/^Version: //p' "$project/packaging/control")
dpkg-deb --root-owner-group --build "$stage" "$output/jatayu-pdf-studio_${version}_all.deb"
