# bash completion for tg (tgsend) — contacts come from ~/.cache/tgsend/completions (your last 100 chats)
# install: tg --install-completion
_tg() {
    local line=${COMP_LINE:0:COMP_POINT} raw="" cur
    # the word under the cursor, keeping backslash-escaped spaces ("John\ Sm")
    [[ $line =~ (([^[:space:]\\]|\\.)*)$ ]] && raw=${BASH_REMATCH[1]}
    cur=${raw//\\/}
    local -a words
    read -ra words <<<"${line% *}"
    local mode=${words[1]} prev=${words[-1]} nargs=$(( ${#words[@]} - 1 ))
    local cache=${XDG_CACHE_HOME:-$HOME/.cache}/tgsend/completions
    local IFS=$'\n' c
    COMPREPLY=()
    compopt -o filenames 2>/dev/null   # bash quotes spaces in names / files for us

    if (( nargs == 0 )) && [[ $cur == -* ]]; then
        COMPREPLY=($(compgen -W $'-t\n-m\n-d\n-f\n-p\n-n\n-l\n--login\n--logout\n--sync\n--help\n-help\n--version\n--install-completion' -- "$cur"))
        return
    fi
    if [[ $mode == -d && $prev == -o ]]; then
        COMPREPLY=($(compgen -d -- "$cur"))
        return
    fi
    if [[ $mode == -m && $nargs == 1 && $cur =~ ^[0-9]+$ ]]; then
        return
    fi
    [[ $prev == -n && $cur =~ ^[0-9]*$ ]] && return
    local pickdir=0 w
    for w in "${words[@]:1}"; do [[ $w == -p || $w == -n ]] && pickdir=1; done

    # contacts (case-insensitive prefix; "@" limits to usernames)
    local lc=${cur,,}
    if [[ -r $cache ]]; then
        while IFS= read -r c; do
            [[ $cur == @* && $c != @* ]] && continue
            [[ ${c,,} == "$lc"* ]] && COMPREPLY+=("$c")
        done <"$cache"
    fi
    # files, only when sending media
    if [[ $mode != -t && $mode != -m && $mode != -d && $cur != @* ]]; then
        if (( pickdir )); then COMPREPLY+=($(compgen -d -- "$cur"))
        else COMPREPLY+=($(compgen -f -- "$cur")); fi
    fi

    # if readline treats "@" as a word break, it only replaces the text after it
    if [[ $COMP_WORDBREAKS == *@* && $cur == *@* ]]; then
        local pre=${cur%@*}@ i
        for i in "${!COMPREPLY[@]}"; do COMPREPLY[i]=${COMPREPLY[i]#"$pre"}; done
    fi
}
complete -F _tg tg tgsend
