# python-prompt

A small python script for my personal prompt used in combination with `zsh`. I  wanted
to have my own prompt with custom features but was honestly shocked of the syntax after
looking at existing prompts 🤯

This is merely a dump of my existing implementation, but maybe someone is interested
(and no particular fan of shell syntax as well) and wants to take a look. In case of
question or errors please do not hesitate to open an issue.

## Asynchronous

Whereas the first version of this prompt was synchronous and not running outside the
shell the current one is. This has the massive advantage of having one thread serving
all shells, communicating via Unix-Sockets. Previously you had to include `echo
$(path/to/prompt.py) | source /dev/stdin` inside your `.zshrc` meaning that every time
a new prompt had to be a drawn a python thread was raised and killed.

## Ideas

Thanks to the external thread (see above) startup time is not critical anymore, leading
to the following ideas:

- Prompt configuration via config file (previously dismissed due to the startup overhead
  by parsing the file)
- systemd-socket activation would be cool, but i am having trouble listening on the
  passed file descriptor with an async server

## Requirements

- Python 3.6+

### Systemd User service

Drop the following lines into `~/.config/systemd/user/python_prompt.service`

```ini
[Unit]
Description=Unit file for the python_prompt socket process

[Service]
ExecStart=/path/to/async_prompt.py

[Install]
WantedBy=default.target
```

Start and enable via `systemctl --user daemon-reload; systemctl --user enable --now
python_prompt`. The default socket path is `$XDG_RUNTIME_DIR/python_prompt.socket`.

### `.zshrc`

- Two functions are needed:

```bash
# see man zshmisc for an explanation
function preexec() {
	export LAST_CMD="${1}"
}
function precmd() {
	# This has be to done before the call to tput, otherwise its return code is
	# captured
	export LAST_EXIT_CODE="$?"
	export COLS="$(tput cols)"
	# separate every line with a 0-byte
	env -0 | nc -U "$XDG_RUNTIME_DIR/python_prompt.socket"| source /dev/stdin
}

```
