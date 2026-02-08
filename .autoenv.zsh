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
        gen-card "$zh" "$pinyin" "$other"
    done
  done
}

gen-card() {
  local zh="${1:?}"
  local pinyin="${2:?}"
  local other="${3:?}"

  cat <<EOF
Q: ${zh}
A:

${pinyin}

${other}

---

EOF
}

alias start='systemctl --user start hashcards.service'
alias stop='systemctl --user stop hashcards.service'
alias status='systemctl --user status hashcards.service'
alias restart='systemctl --user restart hashcards.service'
alias atus=status
alias art=start
alias logs='journalctl --user --unit hashcards.service'
