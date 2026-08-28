import { el } from '../util.js';

/** Simple modal. Returns a close() function. */
export function modal({ title, body, actions = [], onClose = null, wide = false }) {
  const back = el('div', { class: 'modal-back' });
  const close = () => { back.remove(); if (onClose) onClose(); };
  back.addEventListener('click', (e) => { if (e.target === back) close(); });
  document.addEventListener('keydown', function esc(e) {
    if (e.key === 'Escape') { close(); document.removeEventListener('keydown', esc); }
  });

  const node = el('div', { class: 'modal', style: wide ? { width: 'min(860px, 100%)' } : {} }, [
    el('div', { class: 'spread' }, [
      el('h3', { text: title }),
      el('button', { class: 'btn ghost sm', text: 'Close', onclick: close }),
    ]),
    el('div', { style: { marginTop: '14px' } }, [body]),
    actions.length
      ? el('div', { class: 'modal-actions' }, actions.map(a => el('button', {
        class: 'btn ' + (a.kind || 'ghost'),
        text: a.label,
        onclick: () => a.run(close),
      })))
      : null,
  ]);
  back.appendChild(node);
  document.body.appendChild(back);
  return close;
}

export function confirmDialog(message, onYes, { danger = true, label = 'Delete' } = {}) {
  modal({
    title: 'Are you sure?',
    body: el('p', { class: 'muted', text: message }),
    actions: [{ label, kind: danger ? 'danger' : '', run: (close) => { close(); onYes(); } }],
  });
}
