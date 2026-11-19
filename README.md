# tgsend

Send files and messages to Telegram from your terminal, as **yourself**: no bot and no quotes needed.

```bash
tg photo.jpg video.mp4 @bob           # send files (photos/videos go as one album)
tg -t running 5 min late John Smith   # send text, no quotes needed
tg -m 20 @bob                         # read the chat in a readable way
tg -d 0 @bob                          # download the latest photo/file from the chat
```

- **Tab completion** for recipients: `@bo<TAB>` → `@bobby`, `jo<TAB>` → `John\ Smith`, built from your 100 most recent chats
- **Names work like in the app**: use the name *you* saved a contact under, or just part of it (`bob`)
- **`-l`** sends to the last person you sent something to with `tg`
- **File picker** (`-p`) with fuzzy search and preview, or **send the newest N files** (`-n 5`)
- **Readable history** with day headers, replies, forwards, and numbered media you can download
- Progress bars, albums, uncompressed sending (`-f`), multi-line text from stdin

## Install

**Requirements:** Python 3.10+, [pipx](https://pipx.pypa.io) or [uv](https://docs.astral.sh/uv/) to install it, and optionally
[fzf](https://github.com/junegunn/fzf) for the file picker (`-p`) and `bash-completion` for tab completion.

### Arch Linux / Manjaro / EndeavourOS / Omarchy

```bash
sudo pacman -S --needed python-pipx fzf bash-completion
pipx ensurepath
pipx install "tgsend[fast] @ git+https://github.com/protomax-svg/tgsend"
tg --install-completion
```

### Ubuntu / Debian / Linux Mint / Pop!_OS

Works on Ubuntu 22.04+ and Debian 12+.

```bash
sudo apt update
sudo apt install pipx fzf bash-completion
pipx ensurepath
pipx install "tgsend[fast] @ git+https://github.com/protomax-svg/tgsend"
tg --install-completion
```

> Don't use plain `pip install`. Ubuntu 23.04+ and Debian 12+ block it with an
> `externally-managed-environment` error. That's expected; pipx is the right tool.
>
> On **older releases** (Ubuntu 20.04, Debian 11), the system Python is too old. Use the uv method below, which
> downloads a newer Python for you.

### Fedora

```bash
sudo dnf install pipx fzf bash-completion
pipx ensurepath
pipx install "tgsend[fast] @ git+https://github.com/protomax-svg/tgsend"
tg --install-completion
```

### Any other Linux (with uv)

[uv](https://docs.astral.sh/uv/) needs no system packages, and it installs a suitable Python by itself if yours is too old:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
uv tool install "tgsend[fast] @ git+https://github.com/protomax-svg/tgsend"
tg --install-completion
```

Install `fzf` with your package manager if you want the file picker.

### After installing

- **Open a new terminal**, so the `tg` command (from `pipx ensurepath`) and tab completion become available.
- **`tg: command not found`?** Make sure `~/.local/bin` is in your `PATH`. Run `pipx ensurepath` or `uv tool update-shell`, then open a new terminal.
- **`[fast]`** adds `cryptg` for much faster uploads and downloads. If it fails to install on your system, run
  the same command without `[fast]`.

### Update

```bash
pipx reinstall tgsend        # or: uv tool upgrade tgsend
```

### Uninstall

```bash
tg --logout                  # ends the Telegram session and deletes it
pipx uninstall tgsend        # or: uv tool uninstall tgsend
rm -rf ~/.config/tgsend ~/.local/share/tgsend ~/.cache/tgsend \
       ~/.local/share/bash-completion/completions/{tg,tgsend}
```

## Setup (once)

1. Go to **https://my.telegram.org** → *API development tools* and create an app (any name). Copy the `api_id` and `api_hash`.
2. Run `tg --login`. It asks for the api_id and api_hash, your phone number, the login code Telegram sends you, and your 2FA password if you have one.

Your API keys are personal: don't share them or put them in a repo. tgsend stores them with `600` permissions in `~/.config/tgsend/`.

## Usage

| Command | What it does |
|---|---|
| `tg FILE... TO` | send files; 2+ photos/videos go as an album |
| `tg -f FILE... TO` | send uncompressed, as files |
| `tg -p [DIR] TO` | pick files interactively (TAB select, Enter send) |
| `tg -n N [DIR] TO` | send the N newest files in DIR (asks first) |
| `tg -t TEXT... TO` | send text, no quotes needed |
| `echo hi \| tg -t TO` | send text from stdin |
| `tg -m [N] TO` | show the last N messages (default 20) |
| `tg -d SEL... TO [-o DIR]` | download media: `0` = newest, `0-4` range, or file name |
| `tg --sync` | refresh the chat list used for tab completion |
| `tg --logout` | log out and delete the session |
| `tg -help` | full guide |

**`TO` (recipient)** can be:
- `@username`
- the contact's name as you saved it (`John Smith`, no quotes needed)
- a unique part of the name (`john`)
- `me` for Saved Messages
- `-l` for the last person you sent to with `tg`. Put it first or last: `tg -l pic.png`, `tg -t hi -l`

If a name matches more than one chat, `tg` lists the matches and sends nothing. Every send prints `✓ … → Name`.

**Shell quoting:** text needs no quotes, but your shell still interprets `' " ; & | * ? $ !`.
For messages with those characters, quote them: `tg -t "don't forget!" @bob`.

## Files

| Path | Contents |
|---|---|
| `~/.config/tgsend/config.json` | your api_id / api_hash |
| `~/.local/share/tgsend/session.session` | your login. **This gives full account access. Keep it private.** |
| `~/.local/share/tgsend/last_recipient.json` | who `-l` sends to |
| `~/.cache/tgsend/` | recent chats for tab completion |

## Troubleshooting

- `TG_DEBUG=1 tg ...` shows the full error
- `NO_COLOR=1 tg ...` turns off colours
- Name not found: run `tg --sync` or use the `@username`
- Telegram rate-limits accounts that send very fast, so don't use this for bulk messaging or spam.

## How it works

tgsend logs in as your own Telegram account through the official MTProto API, using
[Telethon](https://github.com/LonamiWebs/Telethon). It isn't a bot, so it can message anyone you could message from the app.

## License

MIT
