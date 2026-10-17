#!/usr/bin/env bash
# One-shot setup + build of WN-Turnip on Ubuntu/Debian.
#
# Installs every dependency, downloads the Android NDK, clones or updates this
# fork, builds the driver and copies the zip to ~/WinNative-builds.
# Safe to run again: anything already present is skipped.
#
#   bash setup_and_build.sh                 # balanced variant (b)
#   VARIANT=p bash setup_and_build.sh       # performance variant
#   BRANCH=main bash setup_and_build.sh     # another branch of the fork
#   BASE_DIR=/mnt/build bash setup_and_build.sh   # work on another disk (sources, NDK, build)
#
# Run without downloading it first:
#   bash <(curl -fsSL https://raw.githubusercontent.com/durunduk/DriversWN/feature/a8xx-winnative/setup_and_build.sh)

set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/durunduk/DriversWN.git}"
BRANCH="${BRANCH:-feature/a8xx-winnative}"
VARIANT="${VARIANT:-b}"
BASE_DIR="${BASE_DIR:-$HOME}"
SRC_DIR="${SRC_DIR:-$BASE_DIR/DriversWN}"
NDK_VER="android-ndk-r26d"
NDK_DIR="${ANDROID_NDK_HOME:-$BASE_DIR/$NDK_VER}"
OUT_DIR="${OUT_DIR:-$HOME/WinNative-builds}"
MIN_MESON="1.4.0"

step() { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }
fail() { printf '\n\033[1;31mERROR:\033[0m %s\n' "$*" >&2; exit 1; }

[ "$(id -u)" -ne 0 ] || fail "Run as your normal user, not root (sudo is used where needed)."
command -v apt-get >/dev/null || fail "This script supports Ubuntu/Debian (apt) only."

# ------------------------------------------------------------------ disk space
mkdir -p "$BASE_DIR" 2>/dev/null || fail "Cannot create $BASE_DIR"
[ -w "$BASE_DIR" ] || fail "$BASE_DIR is not writable by $(whoami) (sudo chown $(whoami): $BASE_DIR)"
free_gb=$(( $(df -Pk "$BASE_DIR" | awk 'NR==2 {print $4}') / 1024 / 1024 ))
[ "$free_gb" -ge 6 ] || fail "Need at least 6 GB free in $BASE_DIR, have ${free_gb} GB."

# ------------------------------------------------------------------ packages
step "Installing packages (sudo password may be asked)"
sudo apt-get update -qq
sudo apt-get install -y -qq git curl unzip zip patchelf flex bison ninja-build \
	glslang-tools python3 python3-pip python3-mako python3-yaml python3-packaging \
	pipx meson >/dev/null

export PATH="$HOME/.local/bin:$PATH"

# Mesa main needs a newer meson than older Ubuntu releases ship.
meson_ver="$(meson --version 2>/dev/null || echo 0)"
if ! dpkg --compare-versions "$meson_ver" ge "$MIN_MESON"; then
	step "meson $meson_ver is too old, installing a current one with pipx"
	pipx install --force meson >/dev/null
	hash -r
	meson_ver="$(meson --version)"
	dpkg --compare-versions "$meson_ver" ge "$MIN_MESON" || fail "meson is still $meson_ver"
fi
echo "meson $meson_ver"

# build_turnip.sh checks for a `glslang` command; some releases only ship glslangValidator.
if ! command -v glslang >/dev/null; then
	mkdir -p "$HOME/.local/bin"
	ln -sf "$(command -v glslangValidator)" "$HOME/.local/bin/glslang"
fi
# It also checks for `pip`.
if ! command -v pip >/dev/null; then
	mkdir -p "$HOME/.local/bin"
	ln -sf "$(command -v pip3)" "$HOME/.local/bin/pip"
fi

# ------------------------------------------------------------------ NDK
if [ ! -x "$NDK_DIR/toolchains/llvm/prebuilt/linux-x86_64/bin/clang" ]; then
	step "Downloading $NDK_VER (about 1 GB, once)"
	tmp_zip="$BASE_DIR/$NDK_VER-linux.zip"
	curl -fL --retry 3 -o "$tmp_zip" "https://dl.google.com/android/repository/$NDK_VER-linux.zip"
	rm -rf "$BASE_DIR/$NDK_VER"
	unzip -q "$tmp_zip" -d "$BASE_DIR"
	rm -f "$tmp_zip"
	NDK_DIR="$BASE_DIR/$NDK_VER"
fi
export ANDROID_NDK_HOME="$NDK_DIR"
echo "NDK: $ANDROID_NDK_HOME"

# ------------------------------------------------------------------ sources
step "Getting DriversWN ($BRANCH)"
if [ -d "$SRC_DIR/.git" ]; then
	cd "$SRC_DIR"
	if [ -n "$(git status --porcelain --untracked-files=no)" ]; then
		git status --short --untracked-files=no
		fail "$SRC_DIR has local changes (listed above). Commit/stash them or move the folder away."
	fi
	git fetch origin "$BRANCH"
	git checkout -q -B "$BRANCH" "origin/$BRANCH"
else
	git clone -b "$BRANCH" "$REPO_URL" "$SRC_DIR"
	cd "$SRC_DIR"
fi
echo "Commit: $(git log -1 --format='%h %s')"

# ------------------------------------------------------------------ build
step "Building WN-Turnip variant '$VARIANT' (downloads current Mesa, 10-30 min)"
BUILD_VARIANTS="$VARIANT" ./build_wn_turnip.sh

step "Checking that every patch was applied"
# 0002 (WaveSize(32)) and 0004 (A8XX bindless invalidation) are the ones the
# A8XX rendering fixes depend on; without them the zip is not worth testing.
for n in 0002 0004; do
	grep -q "a8xx-winnative: applied $n" "build_log_${VARIANT}.txt" \
		|| fail "Patch $n of the A8XX series did not apply (see build_log_${VARIANT}.txt). Send that log."
done
if ! ./verify_patches.sh "$VARIANT"; then
	echo "Warning: some other WinNative patches did not apply (lines above)."
	echo "         The driver is still usable; send build_log_${VARIANT}.txt if something looks wrong."
fi

zip_name="WN-Turnip-1.0-${VARIANT}_Axxx.zip"
zip_path="$(dirname "$SRC_DIR")/$zip_name"
[ -f "$zip_path" ] || zip_path="$SRC_DIR/$zip_name"
[ -f "$zip_path" ] || fail "Build finished but $zip_name was not found."

mkdir -p "$OUT_DIR"
mesa_hash="$(cut -c1-10 "$SRC_DIR/mesa_hash.txt" 2>/dev/null || echo unknown)"
out="$OUT_DIR/WN-Turnip-${VARIANT}-$(date +%Y%m%d-%H%M)-mesa-${mesa_hash}-$(git rev-parse --short HEAD).zip"
cp "$zip_path" "$out"

printf '\n\033[1;32mDone:\033[0m %s\n' "$out"
echo "Copy it to the phone and install it in WinNative's driver manager."
