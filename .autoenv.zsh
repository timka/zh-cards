gen-words() {
  local lang=${1:?}
  shift
  for dir in $@ ; do
    paste \
      -d'|' \
      $dir/words.{zh,pinyin,$lang} \
    | while IFS="|" read -r zh pinyin other; do
        [ -z "$zh" -o -z "${pinyin}" -o -z "$other" ] && {
          continue
        }
cat <<EOF
Q: ${zh}
A:
${pinyin}
${other}

---

EOF
    done
  done
}
