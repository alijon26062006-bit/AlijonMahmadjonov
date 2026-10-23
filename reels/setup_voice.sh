#!/usr/bin/env bash
# Скачивает бесплатный нейросетевой голос Piper (русский, «Ирина») в reels/.tools
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)/.tools"
mkdir -p "$DIR"
cd "$DIR"
if [ ! -x piper/piper ]; then
  curl -sSL -o piper.tgz https://github.com/rhasspy/piper/releases/download/2023.11.14-2/piper_linux_x86_64.tar.gz
  tar -xzf piper.tgz && rm piper.tgz
fi
if [ ! -f ru-irinia-medium.onnx ]; then
  curl -sSL -o voice.tgz https://github.com/rhasspy/piper/releases/download/v0.0.2/voice-ru-irinia-medium.tar.gz
  tar -xzf voice.tgz && rm voice.tgz
fi
echo "Голос готов: $DIR"
