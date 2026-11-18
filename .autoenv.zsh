_ZH_CARDS_ROOT=${${(%):-%N}:A:h}

gen() {
  local source=${1:?}
  local lang=${2:?}
  shift 2
  local dir
  local -a files
  (( $# )) || set -- .
  for dir in "$@" ; do
    files+=("$dir/$source.tsv")
  done
  uv run --script "$_ZH_CARDS_ROOT/gen-cards.py" --lang "$lang" "${files[@]}"
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
alias ru-gen-1-words='for i in "$_ZH_CARDS_ROOT"/1/* ; do gen-words ru "$i" > Lesson-${i:t}.md ; done'
alias ru-gen-2-words='for i in "$_ZH_CARDS_ROOT"/2/* ; do gen-words ru "$i" > Lesson-${i:t}.md ; done'
alias ru-gen-我一定要找到她…-words='gen-words ru "$_ZH_CARDS_ROOT/我一定要找到她…" > 我一定要找到她….md'
