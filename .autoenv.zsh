gen() {
  local source=${1:?}
  local lang=${2:?}
  shift 2
  for dir in $@ ; do
    paste \
      -d'|' \
      $dir/$source.{zh,pinyin,$lang} \
    | while IFS="|" read -r zh pinyin other; do
        [ -z "$zh" -o -z "${pinyin}" -o -z "$other" ] && {
          continue
        }
        gen-card "$zh" "$pinyin" "$other"
    done
  done
}

alias gen-words='gen words'
alias gen-extra-words='gen extra-words'

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
alias ru-gen-1-words='for i in 1/* ; do gen-words ru $i > Lesson-${i:t}.md ; done'
alias ru-gen-2-words='for i in 2/* ; do gen-words ru $i > Lesson-${i:t}.md ; done'
alias ru-gen-我一定要找到她…-words='gen-words ru > 我一定要找到她….md'
alias start='systemctl --user start hashcards.service'
alias stop='systemctl --user stop hashcards.service'
alias status='systemctl --user status hashcards.service'
alias restart='systemctl --user restart hashcards.service'
alias atus=status
alias art=start
alias logs='journalctl --user --unit hashcards.service'
