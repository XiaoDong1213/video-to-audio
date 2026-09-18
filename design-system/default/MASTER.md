# Design System Master: Video to audio

> 基于 ui-ux-pro-max：Minimalism & Swiss Style  
> 为 **桌面媒体工具** 覆写为浅色方案（避免暗色/玫红默认倾向）

## Product
- Type: Desktop media converter / audio merge utility
- Audience: 日常用户，本地文件处理
- Platform: Windows desktop (PyQt)

## Style
- Name: Minimalism & Swiss Style (light)
- Keywords: clean, functional, spacious, high contrast, sans-serif, grid
- Avoid: purple gradients, cream+terracotta AI look, dark-by-default, emoji icons

## Colors
| Role | Hex |
|------|-----|
| Background | `#F1F5F9` |
| Foreground | `#0F172A` |
| Card | `#FFFFFF` |
| Muted | `#E2E8F0` |
| Muted Foreground | `#64748B` |
| Border | `#E2E8F0` |
| Primary / Brand | `#0F172A` |
| Accent / CTA | `#0284C7` |
| On Accent | `#FFFFFF` |
| Success | `#0D9488` |
| Destructive | `#DC2626` |
| Focus Ring | `#0284C7` |

## Typography
- UI: Microsoft YaHei UI / Segoe UI (desktop native)
- Scale: 12 / 13 / 14 / 16 / 22
- Log: Consolas / Cascadia Mono

## Layout
- Header brand + mode switch
- Left: file list + empty state + actions
- Right: output settings (quality chips prominent)
- Footer: progress + primary CTA
- Spacing rhythm: 8 / 12 / 16 / 24

## UX Rules
- Empty state with clear next action
- Active mode visually indicated
- Progress always visible during work
- Primary CTA contrast ≥ 4.5:1
- Clickable controls: pointing hand cursor
- Focus: visible outline on keyboard focus
