# python-prompt

A small python script for my personal prompt used in combination with `zsh`. I 
wanted to have my own prompt with custom features but was honestly shocked of 
the syntax after looking at existing prompts 🤯

This is merely a dump of my existing implementation, but maybe someone is 
interested (and no particular fan of shell syntax as well) and wants to take a 
look. In case of question or errors please do not hesitate to open an issue.

## Requirements

- Python 3.6+
- Two functions inside your `.zshrc` are needed:

```bash
# see man zshmisc
function preexec() {
  export LAST_CMD="${2}"
}

# see man zshmisc
function precmd() {
  export LAST_EXIT_CODE="$?"
  echo $(path/to/prompt.py) | source /dev/stdin
}
```

