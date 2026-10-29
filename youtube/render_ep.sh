# render_ep.sh <Composition> <ep>  — рендер кусками по 2700 кадров, затем склейка и звук
cd ~/course/youtube
COMP=$1; EP=$2; OUT=out/$EP; mkdir -p $OUT
EXE=/ms-playwright/chromium_headless_shell-1243/chrome-headless-shell-linux64/chrome-headless-shell
TOTAL=$(python3 -c "import json,math;print(math.ceil(json.load(open('src/data/$EP.json'))['total']*30))")
i=0; s=0
while [ $s -lt $TOTAL ]; do
  e=$(( s + 2699 )); [ $e -ge $TOTAL ] && e=$(( TOTAL - 1 ))
  name=$(printf "p%02d" $i)
  if [ ! -f $OUT/$name.mp4 ]; then
    st=$(date +%s)
    npx remotion render src/index.ts $COMP $OUT/tmp_$name.mp4 --frames=$s-$e --muted --browser-executable=$EXE --concurrency=$(nproc) --log=error > $OUT/$name.log 2>&1 && mv $OUT/tmp_$name.mp4 $OUT/$name.mp4
    echo "$name $s-$e exit=$? sec=$(( $(date +%s) - st ))" >> $OUT/progress.txt
  fi
  s=$(( e + 1 )); i=$(( i + 1 ))
done
cd $OUT
ls p*.mp4 | sort | sed "s/^/file '/; s/$/'/" > list.txt
ffmpeg -v error -y -f concat -safe 0 -i list.txt -c copy video_only.mp4
ffmpeg -v error -y -i video_only.mp4 -i ../../public/$EP/soundtrack.wav -map 0:v -map 1:a -c:v libx264 -preset medium -crf 21 -pix_fmt yuv420p -af loudnorm=I=-14:TP=-1.5:LRA=11 -ar 44100 -c:a aac -b:a 192k -shortest -movflags +faststart final.mp4
ffprobe -v error -show_entries format=duration,size -of compact final.mp4 >> progress.txt
echo ALL_DONE total=$TOTAL >> progress.txt
