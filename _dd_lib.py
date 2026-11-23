# -*- coding: utf-8 -*-
"""详细设计报告配图公共绘图工具（纯 matplotlib）。"""
import os
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Rectangle, Polygon, Ellipse

plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'SimSun']
plt.rcParams['axes.unicode_minus'] = False

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '_figs_dd')
os.makedirs(OUT, exist_ok=True)

EC = '#2B2B2B'
BLUE = '#EAF1FB'
GREEN = '#EAF5EE'
ORANGE = '#FDF2E6'
GREY = '#F3F3F0'
PURPLE = '#F1EDF9'


def canvas(w, h):
    fig = plt.figure(figsize=(w, h), dpi=200)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, w)
    ax.set_ylim(0, h)
    ax.set_axis_off()
    return fig, ax


def save(fig, name):
    path = os.path.join(OUT, name)
    fig.savefig(path, dpi=200, facecolor='white')
    plt.close(fig)
    print('saved', path)


def rect(ax, x, y, w, h, fc='white', ec=EC, lw=1.0, round_=0.0, ls='-', z=2):
    """以左下角 (x, y) 绘制矩形/圆角矩形。"""
    if round_ > 0:
        patch = FancyBboxPatch((x, y), w, h,
                               boxstyle=f'round,pad=0,rounding_size={round_}',
                               fc=fc, ec=ec, lw=lw, ls=ls, zorder=z)
    else:
        patch = Rectangle((x, y), w, h, fc=fc, ec=ec, lw=lw, ls=ls, zorder=z)
    ax.add_patch(patch)


def text(ax, x, y, s, fs=8.2, weight='normal', ha='center', va='center',
         color='#111111', style='normal', z=5, lh=1.35, bbox=None, rotation=0):
    ax.text(x, y, s, ha=ha, va=va, fontsize=fs, fontweight=weight, rotation=rotation,
            color=color, style=style, zorder=z, linespacing=lh, bbox=bbox)


def box(ax, x, y, w, h, title, lines=(), fs=7.6, tfs=8.6, fc='white',
        ec=EC, lw=1.0, round_=0.06, title_color='#111111', align='center'):
    rect(ax, x, y, w, h, fc=fc, ec=ec, lw=lw, round_=round_)
    if lines:
        text(ax, x + w / 2, y + h - 0.20, title, fs=tfs, weight='bold',
             color=title_color)
        body = '\n'.join(lines)
        if align == 'center':
            text(ax, x + w / 2, y + (h - 0.38) / 2 + 0.02, body, fs=fs, lh=1.45)
        else:
            text(ax, x + 0.10, y + h - 0.42, body, fs=fs, ha='left', va='top', lh=1.45)
    else:
        text(ax, x + w / 2, y + h / 2, title, fs=tfs, weight='bold')


def class_box(ax, x, y, w, h, name, stereotype=None, fields=(), methods=(),
              fs=7.0, nfs=8.2, fc='white'):
    """UML 类框：名称区 + 属性区 + 方法区（按条目数动态分配高度）。"""
    rect(ax, x, y, w, h, fc=fc, ec=EC, lw=1.1, round_=0.04)
    head = 0.34 if not stereotype else 0.48
    if stereotype:
        text(ax, x + w / 2, y + h - 0.14, stereotype, fs=6.6, style='italic')
        text(ax, x + w / 2, y + h - 0.32, name, fs=nfs, weight='bold')
    else:
        text(ax, x + w / 2, y + h - head / 2, name, fs=nfs, weight='bold')
    ax.plot([x, x + w], [y + h - head, y + h - head], color=EC, lw=0.8, zorder=3)
    field_h = (len(fields) * 0.165 + 0.10) if fields else 0.0
    ax.plot([x, x + w], [y + h - head - field_h, y + h - head - field_h],
            color=EC, lw=0.8, zorder=3) if (fields and methods) else None
    top = y + h - head - 0.08
    for i, f in enumerate(fields):
        text(ax, x + 0.07, top - i * 0.165, f, fs=fs, ha='left', va='top')
    if methods:
        mtop = y + h - head - field_h - 0.08
        for i, m in enumerate(methods):
            text(ax, x + 0.07, mtop - i * 0.165, m, fs=fs, ha='left', va='top')


def arrow(ax, p1, p2, label=None, rad=0.0, ls='-', lw=1.0, color=EC,
          style='-|>', fs=6.8, lx=None, ly=None, lcolor=EC, z=4, shrink=0,
          bbox=True, ha='center'):
    ax.annotate('', xy=p2, xytext=p1, zorder=z,
                arrowprops=dict(arrowstyle=style, color=color, lw=lw, linestyle=ls,
                                shrinkA=shrink, shrinkB=shrink, mutation_scale=11,
                                connectionstyle=f'arc3,rad={rad}'))
    if label:
        mx = lx if lx is not None else (p1[0] + p2[0]) / 2
        my = ly if ly is not None else (p1[1] + p2[1]) / 2
        text(ax, mx, my, label, fs=fs, color=lcolor, ha=ha,
             bbox=dict(fc='white', ec='none', pad=0.7) if bbox else None, z=z + 2)


def poly_arrow(ax, pts, label=None, lx=None, ly=None, fs=6.8, ls='-'):
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    ax.plot(xs[:-1], ys[:-1], color=EC, lw=1.0, ls=ls, zorder=4)
    ax.annotate('', xy=pts[-1], xytext=pts[-2], zorder=4,
                arrowprops=dict(arrowstyle='-|>', color=EC, lw=1.0, ls=ls,
                                shrinkA=0, shrinkB=0, mutation_scale=11))
    if label:
        text(ax, lx, ly, label, fs=fs, bbox=dict(fc='white', ec='none', pad=0.6), z=6)


def diamond(ax, cx, cy, w, h, s, fs=7.2, fc=ORANGE):
    pts = [(cx, cy + h / 2), (cx + w / 2, cy), (cx, cy - h / 2), (cx - w / 2, cy)]
    ax.add_patch(Polygon(pts, closed=True, fc=fc, ec=EC, lw=1.0, zorder=3))
    text(ax, cx, cy, s, fs=fs, lh=1.25, z=4)


def ellipse(ax, cx, cy, w, h, s, fs=7.6, fc='white'):
    ax.add_patch(Ellipse((cx, cy), w, h, fc=fc, ec=EC, lw=1.0, zorder=3))
    text(ax, cx, cy, s, fs=fs, lh=1.25, z=4)


def title(ax, x, y, s, fs=10.5):
    text(ax, x, y, s, fs=fs, weight='bold')


def seq(ax, participants, messages, top, bottom, head_h=0.42, fs=6.6,
        head_fs=7.2, step=True, note=None):
    """简易时序图。

    participants: [(key, label, x, width, fc)]
    messages: [(from_key, to_key, label, kind, y)]，kind: call / return / self / note
    """
    pos = {}
    for key, label, x, w, fc in participants:
        pos[key] = x
        rect(ax, x - w / 2, top, w, head_h, fc=fc, ec=EC, lw=1.0, round_=0.04)
        text(ax, x, top + head_h / 2, label, fs=head_fs, weight='bold')
        ax.plot([x, x], [bottom, top], color='#555555', lw=0.8, ls=(0, (3, 2)), zorder=1)

    for i, (f, t, label, kind, y) in enumerate(messages):
        if kind == 'self':
            x = pos[f]
            ax.plot([x, x + 0.28, x + 0.28, x], [y + 0.08, y + 0.08, y - 0.08, y - 0.08],
                    color=EC, lw=0.9, zorder=4)
            ax.annotate('', xy=(x, y - 0.08), xytext=(x + 0.28, y - 0.08), zorder=4,
                        arrowprops=dict(arrowstyle='-|>', color=EC, lw=0.9,
                                        shrinkA=0, shrinkB=0, mutation_scale=10))
            text(ax, x + 0.34, y + 0.11, (f'{i + 1}. ' if step else '') + label,
                 fs=fs, ha='left', va='bottom',
                 bbox=dict(fc='white', ec='none', pad=0.5), z=6)
        elif kind == 'note':
            text(ax, pos[f], y, label, fs=fs, ha='left', va='center',
                 bbox=dict(fc='#FFF8D9', ec='#C9B458', pad=1.2), z=6)
        else:
            x1, x2 = pos[f], pos[t]
            ls = '--' if kind == 'return' else '-'
            ax.annotate('', xy=(x2, y), xytext=(x1, y), zorder=4,
                        arrowprops=dict(arrowstyle='-|>' if kind != 'return' else '-|>',
                                        color=EC, lw=0.95, ls=ls, shrinkA=0, shrinkB=0,
                                        mutation_scale=11))
            mx = (x1 + x2) / 2
            text(ax, mx, y + 0.075, (f'{i + 1}. ' if step else '') + label,
                 fs=fs, ha='center', va='bottom',
                 bbox=dict(fc='white', ec='none', pad=0.5), z=6)
