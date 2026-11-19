#!/usr/bin/env python3
"""tgsend — send files & messages to Telegram from the terminal (command: tg)."""
import asyncio
import importlib.resources
import json
import mimetypes
import os
import re
import shutil
import sys
import textwrap
import time
from pathlib import Path

from tgsend import __version__

HOME = Path.home()
CONFIG_DIR = Path(os.environ.get("XDG_CONFIG_HOME", HOME / ".config")) / "tgsend"
DATA_DIR = Path(os.environ.get("XDG_DATA_HOME", HOME / ".local/share")) / "tgsend"
CACHE_DIR = Path(os.environ.get("XDG_CACHE_HOME", HOME / ".cache")) / "tgsend"
CONFIG = CONFIG_DIR / "config.json"
SESSION = DATA_DIR / "session"          # Telethon adds ".session"
PEERS = CACHE_DIR / "peers.json"
COMPLETIONS = CACHE_DIR / "completions"
RECENT_CHATS = 100                      # how many recent chats feed tab completion
CACHE_TTL = 600                         # refresh the chat cache at most every 10 min
NAME_SCAN_LIMIT = 3000                  # how far back `-d <name>` searches

USAGE = """\
usage:
  tg [-f] FILE... TO          send files (photos/videos go as album; -f = send uncompressed as files)
  tg -p [DIR] TO              pick files interactively (fzf; TAB = select, Enter = send)
  tg -n N [DIR] TO            send the N newest files in DIR (default: current folder)
                              (combine: tg -f -n 3 ~/Downloads TO, tg -p -n 50 TO)
  tg -t TEXT... TO            send text (no quotes needed; also: echo hi | tg -t TO)
  tg -m [N] TO                show the last N messages (default 20)
  tg -d SEL... TO [-o DIR]    download media: SEL = index (0 = latest), range 0-4, or file name
  tg --login | --logout | --sync | --install-completion | --version

  TO = @username, the name you saved the contact under, or "me" (Saved Messages).
       -l (first or last argument) = the last person you sent something to with tg:
       tg -l photo.jpg   tg -t hi there -l   tg -m 20 -l   tg -l  (= show it)
       Names may be partial ("bob") if unambiguous. Tab completes from your last 100 chats.

  Full guide with examples: tg -help"""

HELP = """#tgsend — send files & messages to Telegram from the terminal

#SEND FILES
  tg FILE... TO                send one or more files
  tg -f FILE... TO             send uncompressed, as files (keeps full photo/video quality)
  tg -p [DIR] TO               pick files interactively from DIR (default: current folder)
                                 type to filter · TAB select · Ctrl-A all · Ctrl-D none
                                 Enter send · Esc cancel · newest files are listed first
  tg -n N [DIR] TO             send the N newest files in DIR (asks before sending)
  ~ -f, -p and -n combine: tg -p -n 30 ~/Downloads TO · tg -f -n 3 TO
  ~ 2+ photos/videos are sent as an album (10 per album); other files one by one.
  ~ Hidden files and unfinished downloads (.part, .crdownload) are skipped by -p / -n.

#SEND TEXT
  tg -t TEXT... TO             no quotes needed: tg -t see you at 8 @bob
  echo TEXT | tg -t TO         or pipe text in (multi-line works)
  ~ The shell still treats ' " ; & | ( ) * ? $ ! specially — for text with those,
  ~ quote it: tg -t "don't forget!" @bob   (or escape: don\\'t)

#READ MESSAGES
  tg -m [N] TO                 show the last N messages (default 20), oldest at the top
  ~ Media shows as  📎 #0  name (type, size)  — #0 is the newest media in the chat.
  ~ Also shows replies (↪), forwards (⤷) and edits. Reading does NOT mark as read.

#DOWNLOAD MEDIA
  tg -d SEL... TO [-o DIR]     download into the current folder (or DIR)
    SEL = 0                      newest media (numbers as shown by tg -m)
          0-4                    a range
          report.pdf / report    file name, exact or partial (searches ~3000 messages back)
  ~ Several at once: tg -d 0 2 5-7 invoice @bob -o ~/Downloads
  ~ Existing files are never overwritten — you get "name (1).ext".

#RECIPIENTS (TO)
  @username                    any Telegram user, group or channel
  John Smith                   the name YOU saved the contact under; no quotes needed
  john / smi                   a partial name works if only one chat matches
  me                           your Saved Messages (good for testing)
  -l                           the last person you sent something to with tg
                                 put it first or last: tg -l photo.jpg · tg -t hi -l
                                 tg -l on its own = tg -m 20 -l
  ~ If a name matches several chats, tg lists them and sends nothing.
  ~ Every send prints "✓ … → Name" so you always see where it went.

#TAB COMPLETION
  @bh<TAB> → @bhhhh   jo<TAB> → John\\ Smith   (case-insensitive, any alphabet)
  ~ Uses your 100 most recent chats, refreshed automatically every 10 minutes.
  ~ Completes files when sending, folders after -p / -n / -o.

#SETUP & ACCOUNT
  tg --login                   log in (asks for api_id/api_hash from my.telegram.org,
                                 phone, login code, 2FA password)
  tg --sync                    refresh the chat list for tab completion right now
  tg --logout                  log out and delete the session
  tg --install-completion      install bash tab completion (then open a new terminal)
  tg --version                 show the version
  tg -help, -h, --help, --h    this guide (tg with no arguments = short usage)

#EXAMPLES
  tg screenshot.png @bob                 tg *.jpg John Smith
  tg -p ~/Pictures -l                    tg -n 5 ~/Downloads me
  tg -t running 5 min late -l            tg -m 50 bob
  tg -d 0 -l                             tg -d 0-9 @bob -o ~/Pictures/from-bob

#FILES
  ~/.local/share/tgsend/session.session      your login — full account access, keep it private
  ~/.local/share/tgsend/last_recipient.json  who -l sends to
  ~/.config/tgsend/config.json               api_id / api_hash
  ~/.cache/tgsend/                           chat list used by tab completion
  ~/.local/share/bash-completion/completions/tg   tab completion (tg --install-completion)

#TROUBLESHOOTING
  TG_DEBUG=1 tg ...            show the full error instead of a one-line message
  NO_COLOR=1 tg ...            disable colours
  "not logged in"              run tg --login
  name not found               tg --sync, or use @username"""


def show_help():
    out = []
    for line in HELP.split("\n"):
        if line.startswith("#"):
            out.append(c(line[1:], "1;36" if out else "1"))
        elif line.startswith("  ~ "):
            out.append(c("    " + line[4:], "2"))
        else:
            m = re.match(r"^(  )(\S.*?)(\s{2,}.*)?$", line)
            out.append(m.group(1) + c(m.group(2), "1") + (m.group(3) or "") if m and COLOR else line)
    text = "\n".join(out) + "\n"
    rows = shutil.get_terminal_size((80, 24)).lines
    if sys.stdout.isatty() and text.count("\n") >= rows and shutil.which("less"):
        import subprocess
        subprocess.run(["less", "-RFX"], input=text, text=True)
    else:
        sys.stdout.write(text)

# ───────────────────────────── output helpers ─────────────────────────────

COLOR = sys.stdout.isatty() and not os.environ.get("NO_COLOR")


def c(text, code):
    return f"\033[{code}m{text}\033[0m" if COLOR else text


def die(msg, code=1):
    print(f"tg: {msg}", file=sys.stderr)
    sys.exit(code)


def human(n):
    n = float(n or 0)
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024


class Progress:
    """Single-line progress bar on stderr. `album=True` means (files_done, n_files)."""

    def __init__(self, label, album=False):
        self.label, self.album = label, album
        self.start = self.last = time.time()
        self.shown = False

    def __call__(self, cur, total):
        if not sys.stderr.isatty():
            return
        now = time.time()
        if cur < total and now - self.last < 0.1:
            return
        self.last, self.shown = now, True
        frac = cur / total if total else 0
        bar = "█" * int(frac * 24) + "░" * (24 - int(frac * 24))
        if self.album:
            info = f"{int(cur)}/{total} files"
        else:
            speed = cur / max(now - self.start, 1e-6)
            info = f"{human(cur)}/{human(total)}  {human(speed)}/s"
        sys.stderr.write(f"\r\033[K{self.label}  {bar} {frac * 100:5.1f}%  {info}")
        sys.stderr.flush()

    def done(self):
        if self.shown:
            sys.stderr.write("\r\033[K")
            sys.stderr.flush()


# ───────────────────────────── config / client ─────────────────────────────

def load_config():
    try:
        cfg = json.loads(CONFIG.read_text())
        return int(cfg["api_id"]), cfg["api_hash"]
    except (OSError, ValueError, KeyError):
        return None


def make_client(cfg):
    from telethon import TelegramClient
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    os.chmod(DATA_DIR, 0o700)
    return TelegramClient(str(SESSION), cfg[0], cfg[1],
                          device_model="tgsend", app_version=__version__)


async def connect():
    cfg = load_config()
    if not cfg:
        die("not set up yet — run: tg --login")
    client = make_client(cfg)
    await client.connect()
    if not await client.is_user_authorized():
        await client.disconnect()
        die("not logged in — run: tg --login")
    return client


# ───────────────────────────── chat cache ─────────────────────────────

def load_peers():
    try:
        return json.loads(PEERS.read_text())
    except (OSError, ValueError):
        return []


def peers_stale():
    try:
        return time.time() - PEERS.stat().st_mtime > CACHE_TTL
    except OSError:
        return True


def clean(s):
    return re.sub(r"\s+", " ", s or "").strip()


async def sync_peers(client):
    from telethon import utils
    peers = []
    async for d in client.iter_dialogs(limit=RECENT_CHATS):
        e = d.entity
        if getattr(e, "is_self", False):
            name = "Saved Messages"
        else:
            name = clean(utils.get_display_name(e))   # for contacts: the name YOU saved
        uname = getattr(e, "username", None)
        if not uname and getattr(e, "usernames", None):
            active = [u.username for u in e.usernames if u.active]
            uname = active[0] if active else None
        kind = ("bot" if getattr(e, "bot", False) else "user") if d.is_user else \
               ("channel" if d.is_channel and not d.is_group else "group")
        if name or uname:
            peers.append({"id": d.id, "name": name, "username": uname, "kind": kind})

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    tmp = PEERS.with_suffix(".tmp")
    tmp.write_text(json.dumps(peers, ensure_ascii=False, indent=1))
    tmp.replace(PEERS)

    words, seen = ["me"], {"me"}
    for p in peers:
        for w in ((f"@{p['username']}" if p["username"] else None), p["name"]):
            if w and w.lower() not in seen:
                seen.add(w.lower())
                words.append(w)
    tmp = COMPLETIONS.with_suffix(".tmp")
    tmp.write_text("\n".join(words) + "\n")
    tmp.replace(COMPLETIONS)
    return peers


def match_name(query, peers):
    """Return matches for a name, best tier first: exact > prefix > word-prefix > substring."""
    q = query.casefold().lstrip("@") if query.startswith("@") else query.casefold()
    tiers = [
        lambda p: p["name"].casefold() == q or (p["username"] or "").casefold() == q,
        lambda p: p["name"].casefold().startswith(q),
        lambda p: any(w.startswith(q) for w in p["name"].casefold().split()),
        lambda p: q in p["name"].casefold(),
    ]
    for test in tiers:
        hits = [p for p in peers if test(p)]
        if hits:
            return hits
    return []


def split_target(args, peers, need_payload=True):
    """Recipient is the last argument — or the last few words if they form an exact name."""
    if not args or (need_payload and len(args) < 2):
        return None, None
    names = {p["name"].casefold() for p in peers}
    for k in range(min(4, len(args) - need_payload), 1, -1):
        cand = " ".join(args[-k:])
        if cand.casefold() in names:
            return args[:-k], cand
    return args[:-1], args[-1]


LATEST = "\0latest"            # stands in for the recipient when -l is used
LAST_SENT = DATA_DIR / "last_recipient.json"


def remember_recipient(entity, who):
    """Called after every successful send, so `-l` can reuse this recipient."""
    from telethon import utils
    try:
        LAST_SENT.write_text(json.dumps({"id": utils.get_peer_id(entity), "who": who},
                                        ensure_ascii=False))
    except (OSError, TypeError, ValueError):
        pass


async def resolve_latest(client):
    """The last recipient you sent something to with tg."""
    try:
        last = json.loads(LAST_SENT.read_text())
    except (OSError, ValueError):
        die("-l = last person you sent to with tg, but you haven't sent anything yet")
    try:
        return await client.get_input_entity(last["id"]), last["who"]
    except ValueError:
        return await client.get_entity(last["id"]), last["who"]


async def resolve(client, query, peers):
    from telethon import utils
    if query == LATEST:
        return await resolve_latest(client)
    q = query.strip()
    if q.lower() in ("me", "self", "saved", "saved messages"):
        return await client.get_me(), "Saved Messages"
    m = re.match(r"^(?:https?://)?(?:t\.me/|@)([A-Za-z0-9_]{4,})/?$", q)
    if m:
        uname = m.group(1)
        for p in peers:
            if (p["username"] or "").casefold() == uname.casefold():
                try:
                    return await client.get_input_entity(p["id"]), label(p)
                except ValueError:
                    break
        try:
            e = await client.get_entity(uname)
        except (ValueError, TypeError):
            die(f"no Telegram user/chat called @{uname}")
        return e, f"{utils.get_display_name(e)} (@{uname})"
    if re.fullmatch(r"-?\d+", q):
        e = await client.get_entity(int(q))
        return e, utils.get_display_name(e)

    hits = match_name(q, peers)
    if not hits:  # not in recent chats: look through your saved contacts too
        from telethon.tl.functions.contacts import GetContactsRequest
        res = await client(GetContactsRequest(hash=0))
        extra = [{"id": u.id, "name": clean(utils.get_display_name(u)),
                  "username": u.username, "kind": "user"} for u in res.users]
        hits = match_name(q, extra)
    if not hits:
        die(f'nobody matching "{q}" in your recent chats or contacts')
    if len(hits) > 1:
        lines = "\n".join(f"  {label(p)}" for p in hits[:15])
        die(f'"{q}" is ambiguous, did you mean:\n{lines}')
    try:
        return await client.get_input_entity(hits[0]["id"]), label(hits[0])
    except ValueError:
        return await client.get_entity(hits[0]["id"]), label(hits[0])


def label(p):
    return f"{p['name']} (@{p['username']})" if p.get("username") else p["name"]


# ───────────────────────────── media helpers ─────────────────────────────

def is_media(m):
    from telethon.tl.types import MessageMediaDocument, MessageMediaPhoto
    return isinstance(m.media, (MessageMediaPhoto, MessageMediaDocument)) and m.file is not None


def media_kind(m):
    if m.photo: return "photo"
    if m.sticker: return "sticker"
    if m.gif: return "gif"
    if m.video_note: return "videonote"
    if m.video: return "video"
    if m.voice: return "voice"
    if m.audio: return "audio"
    return "file"


def media_name(m):
    name = m.file.name
    if name:
        name = os.path.basename(name.replace("\\", "/")).strip() or None
    if not name:
        name = f"{media_kind(m)}_{m.id}{m.file.ext or ''}"
    return name


def media_desc(m):
    bits = [media_kind(m)]
    dur = getattr(m.file, "duration", None)
    if dur:
        bits.append(f"{int(dur) // 60}:{int(dur) % 60:02d}")
    bits.append(human(m.file.size))
    return f"{media_name(m)}  ({', '.join(bits)})"


def is_visual(path):
    mime = mimetypes.guess_type(path)[0] or ""
    return mime.startswith(("image/", "video/")) and not mime.endswith(("gif", "svg+xml", "webp"))


# ───────────────────────────── commands ─────────────────────────────

async def cmd_login():
    cfg = load_config()
    if not cfg:
        print("One-time setup. Get your API id/hash at https://my.telegram.org → API development tools.")
        api_id = input("api_id: ").strip()
        api_hash = input("api_hash: ").strip()
        if not api_id.isdigit() or not re.fullmatch(r"[0-9a-f]{32}", api_hash):
            die("that doesn't look like a valid api_id / api_hash")
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        CONFIG.write_text(json.dumps({"api_id": int(api_id), "api_hash": api_hash}))
        os.chmod(CONFIG, 0o600)
        cfg = (int(api_id), api_hash)
    client = make_client(cfg)
    await client.start()                         # asks for phone, code, 2FA password
    os.chmod(f"{SESSION}.session", 0o600)
    me = await client.get_me()
    peers = await sync_peers(client)
    print(f"Logged in as {me.first_name} (@{me.username or '-'}). Cached {len(peers)} recent chats.")
    await client.disconnect()


def cmd_install_completion():
    data = Path(os.environ.get("XDG_DATA_HOME", HOME / ".local/share"))
    dest = data / "bash-completion" / "completions"
    dest.mkdir(parents=True, exist_ok=True)
    script = importlib.resources.files("tgsend").joinpath("completions/tg.bash").read_text()
    for cmd in ("tg", "tgsend"):
        (dest / cmd).write_text(script)
    print(f"Installed bash completion to {dest}/tg — open a new terminal to use it.")
    if not Path("/usr/share/bash-completion/bash_completion").exists():
        print("Note: needs the bash-completion package (Arch: sudo pacman -S bash-completion).")


async def cmd_logout():
    cfg = load_config()
    if cfg:
        client = make_client(cfg)
        await client.connect()
        if await client.is_user_authorized():
            await client.log_out()
        await client.disconnect()
    for f in (PEERS, COMPLETIONS, Path(f"{SESSION}.session")):
        f.unlink(missing_ok=True)
    print("Logged out (API id/hash kept in ~/.config/tgsend/config.json).")


SKIP_SUFFIXES = (".part", ".crdownload", ".tmp", ".swp", "~")


def list_files(root, recursive):
    """Non-hidden files under root, newest first."""
    out = []
    if recursive:
        base = len(root.parts)
        for dirpath, dirs, files in os.walk(root):
            dirs[:] = [d for d in dirs if not d.startswith(".")] if len(Path(dirpath).parts) - base < 4 else []
            out += [Path(dirpath) / f for f in files if not f.startswith(".")]
            if len(out) > 20000:
                break
    else:
        out = [e for e in root.iterdir() if not e.name.startswith(".")]
    files = []
    for f in out:
        try:
            if f.is_file() and not f.name.endswith(SKIP_SUFFIXES):
                files.append((f.stat().st_mtime, f))
        except OSError:
            pass
    return [f for _, f in sorted(files, key=lambda x: x[0], reverse=True)]


def ago(ts):
    s = time.time() - ts
    for unit, n in (("d", 86400), ("h", 3600), ("m", 60)):
        if s >= n:
            return f"{int(s // n)}{unit} ago"
    return "just now"


def pick_files(root, who, candidates):
    """Interactive multi-select with fzf. Returns chosen paths (empty = cancelled)."""
    import subprocess
    if not shutil.which("fzf"):
        die("the picker needs fzf (sudo pacman -S fzf)")
    if not candidates:
        die(f"no files in {root}")
    lines = []
    for f in candidates:
        st = f.stat()
        lines.append(f"{ago(st.st_mtime):>8}  {human(st.st_size):>9}\t{f.relative_to(root)}")
    preview = ('f={2}; ls -lh --time-style=+"%Y-%m-%d %H:%M" -- "$f" | cut -d" " -f5-; '
               'file -b -- "$f"; echo; case "$(file -b --mime-type -- "$f")" in '
               'text/*|application/json|application/x-shellscript) head -n 200 -- "$f";; esac')
    r = subprocess.run(
        ["fzf", "--multi", "--reverse", "--height=90%", "--delimiter=\t", "--with-nth=1,2",
         "--nth=2", "--prompt", f"send to {who} › ",
         "--header", "TAB select · Ctrl-A all · Ctrl-D none · Enter send · Esc cancel",
         "--bind", "ctrl-a:select-all,ctrl-d:deselect-all",
         "--preview", preview, "--preview-window=right:45%:wrap"],
        input="\n".join(lines), text=True, stdout=subprocess.PIPE, cwd=root)
    if r.returncode not in (0, 1):
        return []
    return [root / line.split("\t", 1)[1] for line in r.stdout.splitlines() if "\t" in line]


def confirm(question):
    if not sys.stdin.isatty():
        return True
    try:
        return input(f"{question} [Y/n] ").strip().lower() in ("", "y", "yes", "т", "так", "д", "да")
    except EOFError:
        return False


async def cmd_send(client, args, peers, as_file, pick=False, newest=None):
    if pick or newest:
        where, target = split_target(args, peers, need_payload=False)
        if not target:
            die("usage: tg -p [DIR] TO   or   tg -n N [DIR] TO")
        if len(where) > 1:
            die("give at most one folder for -p / -n (default: current folder)")
        root = Path(where[0]).expanduser().resolve() if where else Path.cwd()
        if not root.is_dir():
            die(f"not a folder: {where[0]}")
        entity, who = await resolve(client, target, peers)
        candidates = list_files(root, recursive=pick)
        if newest:
            candidates = candidates[:newest]
        if pick:
            paths = pick_files(root, who, candidates)
            if not paths:
                die("nothing selected", 130)
        else:
            if not candidates:
                die(f"no files in {root}")
            paths = candidates
            print(f"Latest {len(paths)} in {root}:")
            for f in paths:
                print(f"  {ago(f.stat().st_mtime):>8}  {human(f.stat().st_size):>9}  {f.name}")
            if not confirm(f"Send {'these' if len(paths) > 1 else 'it'} to {who}?"):
                die("cancelled", 130)
    else:
        files, target = split_target(args, peers)
        if not target:
            die("usage: tg [-f] FILE... TO")
        paths = []
        for f in files:
            p = Path(f).expanduser()
            if p.is_dir():
                die(f"{f} is a folder — pick from it: tg -p {f} TO   or send all: tg {f.rstrip('/')}/* TO")
            if not p.is_file():
                die(f"not a file: {f}")
            paths.append(p)
        entity, who = await resolve(client, target, peers)
    await send_paths(client, entity, who, paths, as_file)


async def send_paths(client, entity, who, paths, as_file):
    if not as_file and len(paths) > 1 and all(is_visual(p) for p in paths):
        for i in range(0, len(paths), 10):              # Telegram albums hold max 10
            chunk = paths[i:i + 10]
            prog = Progress(f"album ({len(chunk)})", album=True)
            await client.send_file(entity, [str(p) for p in chunk],
                                   progress_callback=prog, supports_streaming=True)
            prog.done()
            print(f"✓ sent album of {len(chunk)} → {who}")
            remember_recipient(entity, who)
        return
    for n, p in enumerate(paths, 1):
        tag = f"[{n}/{len(paths)}] " if len(paths) > 1 else ""
        prog = Progress(tag + p.name)
        await client.send_file(entity, str(p), force_document=as_file,
                               progress_callback=prog, supports_streaming=True)
        prog.done()
        print(f"✓ {tag}{p.name} ({human(p.stat().st_size)}) → {who}")
        remember_recipient(entity, who)


async def cmd_text(client, args, peers):
    whole = " ".join(args)
    only_target = len(args) == 1 or whole.casefold() in {p["name"].casefold() for p in peers}
    if args and only_target and not sys.stdin.isatty():
        text, target = sys.stdin.read().rstrip("\n"), whole
    else:
        words, target = split_target(args, peers)
        if not target:
            die("usage: tg -t TEXT... TO")
        text = " ".join(words)
    if not text.strip():
        die("nothing to send")
    entity, who = await resolve(client, target, peers)
    await client.send_message(entity, text, parse_mode=None, link_preview=True)
    print(f"✓ message → {who}")
    remember_recipient(entity, who)


SENDER_COLORS = ["36", "35", "34", "33", "31", "96", "95", "94"]


async def cmd_messages(client, args, peers, n):
    if not args:
        die("usage: tg -m [N] TO")
    from telethon import utils
    entity, who = await resolve(client, " ".join(args), peers)
    msgs = [m async for m in client.iter_messages(entity, limit=n)]   # newest first
    idx = 0
    media_idx = {}
    for m in msgs:
        if is_media(m):
            media_idx[m.id] = idx
            idx += 1
    by_id = {m.id: m for m in msgs}

    def sender(m):
        if m.out:
            return "You"
        s = m.sender
        if s is None:
            return clean(m.post_author or who.split(" (@")[0])
        name = clean(utils.get_display_name(s))
        return name.split()[0] if name else "?"

    names = [sender(m) for m in msgs]
    width = shutil.get_terminal_size((100, 20)).columns
    col = min(max((len(s) for s in names), default=3), 14)
    indent = 5 + 1 + col + 2   # "HH:MM" + space + name + 2 spaces
    body_w = max(width - indent, 30)
    palette = {}

    print(c(f"━━ {who} ━━ last {len(msgs)} messages", "1"))
    day = None
    for m, who_ in zip(reversed(msgs), reversed(names)):
        local = m.date.astimezone()
        d = local.strftime("%a, %d %b %Y")
        if d != day:
            day = d
            print(c(f"\n── {d} ──", "2"))
        if who_ == "You":
            color = "32"
        else:
            color = palette.setdefault(who_, SENDER_COLORS[len(palette) % len(SENDER_COLORS)])
        head = f"{c(local.strftime('%H:%M'), '2')} {c(who_[:col].ljust(col), color + ';1')}  "
        lines = []
        if m.action:
            act = type(m.action).__name__.removeprefix("MessageAction")
            lines.append(c("· " + re.sub(r"(?<!^)(?=[A-Z])", " ", act).lower(), "2"))
        if m.fwd_from:
            src = m.fwd_from.from_name
            if not src and m.forward and (m.forward.sender or m.forward.chat):
                src = utils.get_display_name(m.forward.sender or m.forward.chat)
            lines.append(c(f"⤷ forwarded from {src or 'someone'}", "2;3"))
        if m.reply_to and m.reply_to.reply_to_msg_id:
            orig = by_id.get(m.reply_to.reply_to_msg_id)
            snip = clean(orig.message)[:50] if orig and orig.message else (
                f"[{media_kind(orig)}]" if orig and is_media(orig) else "earlier message")
            lines.append(c(f"↪ {snip}", "2;3"))
        if is_media(m):
            lines.append(c(f"📎 #{media_idx[m.id]}  {media_desc(m)}", "33"))
        elif m.media and not m.message:
            lines.append(c(f"[{type(m.media).__name__.removeprefix('MessageMedia').lower()}]", "33"))
        for para in (m.message.split("\n") if m.message else []):
            lines.extend(textwrap.wrap(para, body_w) or [""])
        if m.edit_date and not m.action:
            lines[-1] += c(" (edited)", "2")
        print(head + (lines[0] if lines else ""))
        for line in lines[1:]:
            print(" " * indent + line)
    if media_idx:
        print(c(f"\n{len(media_idx)} media — download with: tg -d <#|name> TO", "2"))


async def cmd_download(client, args, peers, outdir):
    sels, target = split_target(args, peers)
    if not target:
        die("usage: tg -d SEL... TO [-o DIR]")
    want_idx, want_names = set(), []
    for s in sels:
        if re.fullmatch(r"\d+", s):
            want_idx.add(int(s))
        elif re.fullmatch(r"\d+-\d+", s):
            a, b = sorted(map(int, s.split("-")))
            want_idx.update(range(a, b + 1))
        else:
            want_names.append(s)
    entity, who = await resolve(client, target, peers)

    found, exact, fuzzy = {}, {}, {}
    i = scanned = 0
    async for m in client.iter_messages(entity):
        scanned += 1
        if is_media(m):
            if i in want_idx:
                found[i] = m
            nm = media_name(m).casefold()
            for w in want_names:
                if w not in exact and nm == w.casefold():
                    exact[w] = m
                elif w not in fuzzy and w.casefold() in nm:
                    fuzzy[w] = m
            i += 1
        if len(found) == len(want_idx) and len(exact) == len(want_names):
            break
        if want_names and scanned >= NAME_SCAN_LIMIT and len(found) == len(want_idx):
            break

    todo = [found[k] for k in sorted(found)]
    for w in want_names:
        m = exact.get(w) or fuzzy.get(w)
        if m:
            todo.append(m)
        else:
            print(f"tg: no media named like \"{w}\" in the last {scanned} messages", file=sys.stderr)
    for k in sorted(want_idx - found.keys()):
        print(f"tg: no media #{k} (chat has {i} media items)", file=sys.stderr)

    out = Path(outdir).expanduser() if outdir else Path.cwd()
    out.mkdir(parents=True, exist_ok=True)
    done = set()
    for m in todo:
        if m.id in done:
            continue
        done.add(m.id)
        name = media_name(m)
        dest = out / name
        stem, ext, n = dest.stem, dest.suffix, 1
        while dest.exists():
            dest = out / f"{stem} ({n}){ext}"
            n += 1
        prog = Progress(name)
        await client.download_media(m, file=str(dest), progress_callback=prog)
        prog.done()
        print(f"✓ {dest} ({human(dest.stat().st_size)})")
    if not todo:
        sys.exit(1)


# ───────────────────────────── entry point ─────────────────────────────

def parse(argv):
    o = {"mode": "send", "args": [], "as_file": False, "n": 20, "out": None,
         "pick": False, "newest": None}
    latest = False
    if argv and argv[0] == "-l":                 # tg -l -t hi   /   tg -l photo.jpg
        latest, argv = True, argv[1:]
    elif len(argv) > 1 and argv[-1] == "-l":     # tg -t hi -l   /   tg -m 20 -l
        latest, argv = True, argv[:-1]
    if latest:
        argv = (argv or ["-m"]) + [LATEST]       # plain `tg -l` shows that chat
    if argv and argv[0] in ("-h", "--h", "-help", "--help", "help"):
        show_help()
        sys.exit(0)
    if not argv:
        print(USAGE)
        sys.exit(1)
    head, rest = argv[0], argv[1:]
    if head in ("--login", "--logout", "--sync"):
        o["mode"] = head[2:]
    elif head in ("-V", "--version"):
        print(f"tgsend {__version__}")
        sys.exit(0)
    elif head == "--install-completion":
        cmd_install_completion()
        sys.exit(0)
    elif head == "-t":
        o["mode"], o["args"] = "text", rest
    elif head == "-m":
        o["mode"] = "messages"
        if rest and rest[0].isdigit():
            o["n"] = int(rest.pop(0))
        o["args"] = rest
    elif head == "-d":
        o["mode"] = "download"
        while "-o" in rest:
            k = rest.index("-o")
            if k + 1 >= len(rest):
                die("-o needs a directory")
            o["out"] = rest[k + 1]
            del rest[k:k + 2]
        o["args"] = rest
    elif head in ("-f", "-p", "-n"):
        args = list(argv)
        while args and args[0] in ("-f", "-p", "-n"):
            flag = args.pop(0)
            if flag == "-f":
                o["as_file"] = True
            elif flag == "-p":
                o["pick"] = True
            elif args and args[0].isdigit() and int(args[0]) > 0:
                o["newest"] = int(args.pop(0))
            else:
                die("-n needs a number, e.g. tg -n 5 @user")
        o["args"] = args
    elif head.startswith("-") and head != "-" and not Path(head).exists():
        die(f"unknown option {head}\n{USAGE}")
    else:
        o["args"] = argv
    return o


async def main(argv):
    o = parse(argv)
    if o["mode"] == "login":
        return await cmd_login()
    if o["mode"] == "logout":
        return await cmd_logout()

    client = await connect()
    try:
        peers = load_peers()
        if o["mode"] == "sync" or not peers:
            peers = await sync_peers(client)
            if o["mode"] == "sync":
                print(f"Cached {len(peers)} recent chats for tab completion.")
                return
        if o["mode"] == "send":
            await cmd_send(client, o["args"], peers, o["as_file"], o["pick"], o["newest"])
        elif o["mode"] == "text":
            await cmd_text(client, o["args"], peers)
        elif o["mode"] == "messages":
            await cmd_messages(client, o["args"], peers, o["n"])
        elif o["mode"] == "download":
            await cmd_download(client, o["args"], peers, o["out"])
        if peers_stale():
            await sync_peers(client)
    finally:
        await client.disconnect()


def run():
    try:
        asyncio.run(main(sys.argv[1:]))
    except KeyboardInterrupt:
        sys.stderr.write("\n")
        sys.exit(130)
    except Exception as e:  # Telegram RPC errors etc. — short message, no traceback
        if os.environ.get("TG_DEBUG"):
            raise
        die(f"{type(e).__name__}: {e}")


if __name__ == "__main__":
    run()
