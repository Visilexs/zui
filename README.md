# zui and pi-desk

**zui** is a small React-style UI library written in Zephyr. **pi-desk** is a
native desktop window for the [pi](https://github.com/earendil-works/pi) coding
agent, built with it. Both are pure Zephyr. SDL3 (window, Wayland, input,
clipboard, GPU renderer), FreeType and fontconfig are loaded at run time
through `extern fn`, which needs a Zephyr compiler with Linux dynamic linking
(`zc --version` lists `linux-extern`).

There is no browser engine. pi-desk uses no CPU while idle and about 60 MB PSS,
most of which is the GPU driver.

## zui

```zephyr
import "lib/ui.zeph"

fn counter(ctx: Ctx) -> El {
    let count = ctx.useInt(0)
    return box(st().pad(24).gapOf(12), [
        text("clicked {count.get()} times"),
        clickable(st().padXY(14, 8).fill(0x3d59a1ff).hover(0x4d69b1ff).round(6),
            [text("+1")], fn() { count.set(count.get() + 1) })
    ])
}

fn main() {
    zuiRun(App{title: "Counter", background: 0x1a1b26ff, render: counter,
        setup: fn() { let f = fontOpen("sans-serif", sc(15)) }}, 480, 320)
}
```

Build any program with `./build.sh <entry.zeph> <output> [-O2]`.

### Components and state

- Render functions return `El` trees.
- Elements are reconciled against the previous render's retained instances,
  by key or by tag and position.
- Hooks (`useInt`, `useBool`, `useStr`) keep their state on those instances,
  and setting a hook's value schedules a re-render. Code outside a component
  calls `invalidate()` to do the same.

### Elements

- `box` and `row`/`col` lay out with a flexbox subset: direction, gap,
  padding, fixed, min and max sizes, grow, align, justify, and absolute
  overlays. `.wrapRows()` lets a row flow its children onto new lines when
  they no longer fit, instead of squeezing them.
- `text` and `rich` hold wrapped text built from styled spans.
- `scroll` can stick to the bottom; set `centerShort = true` on it to centre
  short content vertically (empty states) while it fits the viewport.
- `input` is a multi-line editor.
- `clickable` reacts to hover, press and click; `draggable` reports drags.
- `canvas` paints itself with the drawing primitives (spinners, charts).

### Motion and layers

What CSS transitions, framer-motion and portals do in React:

- Hover backgrounds cross-fade on their own.
- `presence(key, ENTER_RISE, el)` fades an element in when it first appears
  (`ENTER_FADE`, `ENTER_RISE`, `ENTER_DROP`).
- `stagger(ms, els)` delays each child's enter by `i * ms` (list reveals).
- `glide(el)` animates an element to its new layout position with spring
  physics instead of jumping (switch knobs, tab indicators).
- `exitFade(el)` / `exitRise(el)` / `exitDrop(el)` play a short fade-out
  (170ms, rise/drop by 8px) when a keyed element leaves the tree, like
  AnimatePresence — wrap the element, keep its key stable, and it keeps
  drawing while it fades before being removed.
- `faded(el, alpha)` draws a subtree translucent.
- `withTip(el, "text")` shows a tooltip after the pointer rests on it.
- `portal(el)` draws an element above everything, outside its ancestors'
  clips, and gives it the pointer first (menus, popovers).
- Animation only redraws (no re-render), and stops when nothing moves, so an
  idle window still uses no CPU.

`examples/motion.zeph` shows these; `examples/counter.zeph` is a minimal app.

### Kit

`lib/kit.zeph`, modelled on shadcn/ui, Radix, sonner, react-resizable-panels
and react-rnd: `button` (primary, secondary, outline, ghost, danger),
`iconBtn` with a tooltip, `tabs` with a gliding indicator, `switchToggle`,
`checkbox`, `radioRow`, `slider`, `select`, `badge`, `kbdKeys`, `avatar`,
`dot`, `progressBar`, `spinner`, `skeleton`, `card`, `alert`, `popover`,
`toastCard` for sonner-style notifications, `menuItem`, `modal` for
Radix-style dialogs, `splitter` for resizable panels and `resizeHandles`
for resizable floating boxes. Colours and fonts come from the `kit` theme
struct, which an app sets once. `examples/kit.zeph` shows them all:

```sh
./build.sh examples/kit.zeph build/kit && ./build/kit
```

### Rendering

- Glyphs, anti-aliased rounded corners and fills share one texture atlas.
- A frame is one `SDL_RenderGeometry` call per clip region, and the app only
  redraws when something changes.

### Files

| path | what |
|---|---|
| `lib/ffi.zeph` | SDL3, FreeType, fontconfig and libc bindings |
| `lib/gfx.zeph` | atlas, fonts with fallback, batched quads, clipping |
| `lib/ui.zeph` | elements, reconciliation, hooks, layout, input, motion, tooltips, portals, the event loop |
| `lib/kit.zeph` | ready-made components (buttons, tabs, switches, menus, spinners, splitters...) |
| `lib/json.zeph` | JSON parser (never panics) and encoder |
| `lib/proc.zeph` | child processes with non-blocking pipes |
| `lib/hypr.zeph` | Hyprland IPC socket (backs the in-app windows below) |
| `app/pi/` | pi-desk: theme, Markdown, the RPC session model, the view |

## pi-desk

```sh
./install.sh                 # builds with -O2, installs ~/.local/bin/pi-desk and a launcher entry
pi-desk                      # pi in the current folder
pi-desk ~/project            # pi in another folder
pi-desk ~/project -- -c      # anything after -- goes to pi (here: continue the last session)
```

It runs `pi --mode rpc` through the `pi` on your PATH, so wrapper scripts keep
working (for example, one that starts a local model service). Set
`PI_DESK_PI="cmd args"` to use a different command.

It covers everything the CLI does. Built-in commands that RPC supports run
natively. The few that RPC can't do (`/login`, `/logout`, `/scoped-models`,
`/llama`, `/trust`, `/share`, `/bug`, `/changelog`, and moving around inside
`/tree`) open pi's terminal UI on the same session in kitty. When you close
the terminal, the window reconnects. Set `PI_DESK_TERMINAL` to use another
terminal.

- **Composer**
  - `/` opens a command menu covering the built-ins, extension commands,
    prompt templates and skills.
  - `@` searches files in the project. Tab completes paths.
  - `!cmd` runs a shell command and adds its output to the conversation;
    `!!cmd` keeps the output out of the model's context.
  - Attach images with the paperclip (a file picker), paste them with
    Ctrl+V, or drag them in. They show as thumbnails in the composer and in
    the conversation; click one to open it full size. Dropping or picking
    any other file inserts an `@` reference. Thumbnails need ImageMagick
    (`magick`), the picker needs zenity.
  - Ctrl+G edits the prompt in `$VISUAL` / `$EDITOR`. ↑/↓ recall earlier
    prompts.
  - The border colour shows the thinking level, as the CLI's editor border
    does.
- **While pi works:** Enter steers it and Alt+Enter queues a follow-up.
  Alt+↑ returns queued messages to the editor. Esc stops pi and puts queued
  messages back in the editor.
- **Conversation**
  - Markdown with syntax-highlighted code blocks, tables and lists.
  - Thinking blocks are collapsible; Ctrl+T hides them.
  - Tool cards show icons, live status and highlighted output, with coloured
    diffs for `edit`. Ctrl+O expands them all.
  - Tool calls and `!cmd` runs show a timer that counts up while they run and
    keeps the final time afterwards.
  - Text is selectable across paragraphs (Ctrl+C copies it). Messages show
    copy, edit and fork actions on hover. Scrolling is smooth, with a "Jump
    to latest" button.
- **Sessions**
  - The sidebar groups sessions by day and has search, delete and rename.
  - `/resume` (Ctrl+R), `/fork`, `/clone`, `/tree`, `/name`, `/session` and
    `/import`.
  - `/export` writes HTML, or a JSONL copy when the path ends in `.jsonl`.
  - `/compact [instructions]` and `/reload`.
- **Models**
  - Model picker (Ctrl+L or `/model`), Ctrl+P cycles models, Shift+Tab
    cycles thinking levels.
  - Switching to or from a local provider (`fable-local`, `ninfer-local`)
    restarts pi on the same session, so your wrapper starts the right model
    service.
- **Settings (`/settings`):** automatic compaction and retry, steering and
  follow-up delivery, and the thinking and tool-output display.
- **Header telemetry:** generation speed (tok/s, live while a response
  streams), a context meter (click it for the context dock) and the session
  cost sit next to the model picker. The tok/s count starts at the first
  token, so prompt processing isn't included. When the provider doesn't
  stream usage, the count is estimated at about 4 bytes per token and marked
  `~`. The footer shows the folder and session.
- **Context dock (Ctrl+I):** a breakdown of what fills the context window:
  your messages, responses, thinking, tool calls, tool results, shell output
  and summaries. Whatever is left of pi's reported count is shown as "system
  prompt & tools". The dock also lists the largest single items.
- **File dock (Ctrl+E):** the file pi is reading, writing or editing. Edits
  stream in place as the model types them, as a line diff over the real file,
  and a `write` fills in as it streams. The dock opens by itself on the first
  write or edit, unless you closed it. Chips switch to other files pi touched
  this session.
- **Memory dock (Ctrl+M):** the preferences pi has learned from your
  feedback, kept by the `memory-vault` pi extension
  (`~/.pi/agent/extensions/memory-vault.js`) as one Markdown file each in
  `~/.pi/agent/memory/`. When you say what you like or dislike, pi saves or
  updates an entry (you get a "Remembered: …" notice), and every session
  starts with an index of them. The dock groups them by category; hover an
  entry to edit it in your editor or forget it, and **Add** starts a
  "Remember: …" prompt. `/memory` lists them in pi's terminal UI too.
- **In-app windows (Hyprland):** windows opened by anything pi-desk started
  (pi, its shell commands, a game, a browser) show up in a frame inside
  pi-desk instead of joining your desktop layout. Drag the title bar to move
  the frame, any edge or corner to resize it, double-click the bar to
  maximize; dragged near an edge or corner it anchors there and stays put as
  pi-desk resizes, and the pin button picks a corner directly. The size and
  anchor are saved to `~/.config/pi-desk/apps-frame`. Several windows become
  tabs, each with its app's icon and a close button; the buttons minimize the
  frame to a pill in its corner (click the pill or the header's window button
  to bring it back), maximize it, move the window out to the desktop, or
  close it. Closing pi-desk closes them too. How it works: Wayland can't put
  one app's window inside another, so pi-desk loads a small Lua hook into
  Hyprland (`hyprctl eval`) that floats descendant windows and keeps them
  over the frame; pi-desk is a child subreaper, so a program pi starts in
  the background (`cmd &` from a shell that then exits) still counts. Apps
  that hand off to a copy already running (an open Firefox, Steam) open there
  instead, and the terminal and editor pi-desk opens on purpose stay normal
  windows.
- **Layout:** drag the edge of the sidebar or the dock to resize it, and pick
  how wide the conversation gets in `/settings` (Narrow, Medium, Wide or
  Full; all saved to `~/.config/pi-desk/layout`). Icon buttons explain
  themselves in tooltips, and panels, messages and toasts fade in.
- **Interface size:** set it in `/settings`, with Ctrl+= / Ctrl+− (saved to
  `~/.config/pi-desk/zoom`), or with `ZUI_SCALE=1.5`. Ctrl+0 or "Auto" goes
  back to automatic: 150% on 4K and 125% on 1440p-class heights, but only
  when the compositor itself isn't scaling.
- **Extension UI:** select, confirm, input and editor dialogs, plus
  notifications, status entries and widgets.
- **Command palette (Ctrl+K):** every command and action. F1 lists the
  shortcuts.

## Testing

```sh
../zephyr/zc --test --linux tests/json_test.zeph build/json_test && build/json_test
PI_DESK_PI="python3 tools/mock_pi.py" build/pi-desk     # a scripted fake pi; needs no model
# a prompt containing "file" makes the mock stream a real write and edit of ./mock_demo.py
```

`ZUI_SCRIPT` drives any zui app with synthetic input and screenshots, for
example `"wait 500;type hello;key 13;wait 2000;shot /tmp/a.bmp;quit"`. The
window it opens can't take keyboard focus. The other verbs are:

- `click X Y`, `move X Y`, `drag X1 Y1 X2 Y2` and `wheel DY`
- `drop PATH`
- `hover TEXT`
- `seltext FROM|TO`, which selects between two visible strings
- `printsel`

`ZUI_WIDTH=480` lays the app out at that logical width, for testing narrow
windows. `ZUI_PROFILE=1` prints how long each rebuild and draw takes.
