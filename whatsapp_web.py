"""Sebastian 2.5 — zakładka „WhatsApp”: stan połączenia, podgląd i wysyłka przeglądu, historia rozmowy."""
import contextlib, json, time
from pathlib import Path
from flask import abort, flash, redirect, render_template, request, send_file, session

import whatsapp as W


def register(app, s):
    @app.route('/whatsapp')
    def whatsapp_page():
        W.bind(s)
        with contextlib.closing(W.db()) as con:
            briefs = [dict(b) for b in con.execute('SELECT * FROM briefs ORDER BY id DESC LIMIT 5')]
            names = {u['phone']: (u['name'] or '+' + u['phone']) for u in W.family()}
            talk = [dict(r) for r in con.execute(
                "SELECT * FROM (SELECT 'ty' who, kind, text body, received t, note, COALESCE(from_phone,'') phone FROM inbox "
                "UNION ALL SELECT 'sebastian', kind, body, created, COALESCE(error, status), COALESCE(to_phone,'') FROM outbox "
                "WHERE kind<>'make') ORDER BY t DESC LIMIT 60")]
            for m in talk:                       # kto rozmawia: Ty albo osoba z rodziny
                m['person'] = names.get(m['phone'], '+' + m['phone']) if m['phone'] else ''

            info = {k: W.meta_get(con, k, '') for k in ('heartbeat', 'connected', 'linked_as', 'sent:rano', 'mute_until', 'logged_out')}
            info['watch_linked'] = W.meta_get(con, 'watch_linked', '')
            pending = con.execute("SELECT COUNT(*) FROM outbox WHERE status='pending'").fetchone()[0]
            errors = con.execute("SELECT COUNT(*) FROM outbox WHERE status='error'").fetchone()[0]
        watch = None
        if W.C.WA_WATCH:
            with contextlib.suppress(Exception):
                import whatsapp_watch as WW
                n, last = WW.status_counts()
                with contextlib.closing(WW.db()) as wc:
                    row = wc.execute('SELECT data, created FROM digests ORDER BY created DESC LIMIT 1').fetchone()
                    people = [dict(r) for r in wc.execute("SELECT name, summary, updated FROM people WHERE summary<>'' ORDER BY updated DESC LIMIT 100")]
                watch = {'count': n, 'last': last, 'people': people, 'digest': WW.digest_text(json.loads(row['data'])) if row else '',
                         'digest_at': row['created'][:16].replace('T', ' ') if row else ''}
        return render_template('whatsapp.html', watch=watch, c=W.C, checks=W.checks(), briefs=briefs, talk=talk, info=info, family=W.family(),
                               pending=pending, errors=errors, running=W.agent_loaded(), name=W.owner_name(),
                               engine=W.voice_engine(), csrf=session['csrf'])

    @app.route('/whatsapp/akcja', methods=['POST'])
    def whatsapp_action():
        W.bind(s)
        action = request.form.get('akcja', '')
        kind = request.form.get('rodzaj', 'rano')
        if kind not in W.WHAT:
            abort(400)
        with contextlib.closing(W.db()) as con:
            if action == 'preview':
                W.make_brief(con, kind, send=False)
                flash('Podgląd gotowy (niczego nie wysłano) — poniżej tekst i nagranie.')
            elif action == 'send':
                if not W.C.WA_ENABLED:
                    flash('Najpierw skonfiguruj WhatsApp: python sebastian.py wa-setup')
                else:
                    W.enqueue(con, 'make', kind, purpose='manual')
                    flash('Zlecono: usługa w tle złoży przegląd i wyśle go na WhatsApp (zwykle 1–3 minuty).'
                          + ('' if W.agent_loaded() or W.C.WA_TRANSPORT == 'plik' else ' Uwaga: usługa nie działa — python sebastian.py wa-start'))
            elif action == 'test':
                W.enqueue(con, 'text', f"Cześć{', ' + W.owner_name() if W.owner_name() else ''}! Tu Sebastian — wiadomość testowa z panelu. "
                                       "Napisz „pomoc”, żeby zobaczyć, co potrafię.", purpose='manual')
                flash('Wiadomość testowa w kolejce.')
            elif action == 'retry':
                n = con.execute("UPDATE outbox SET status='pending', attempts=0, error=NULL WHERE status='error'").rowcount
                con.commit()
                flash(f'Ponowię wysyłkę: {n}.')
            elif action == 'watch_digest':
                import whatsapp_watch as WW
                WW.digest(cache=True, since=int(time.time() // 3600 * 3600 - 86400), period='z ostatniej doby')
                flash('Podsumowanie WhatsAppa gotowe (niczego nie wysłano).')
            elif action == 'unmute':
                W.meta_set(con, 'mute_until', '')
                flash('Powiadomienia włączone.')
            else:
                abort(400)
        return redirect('/whatsapp')

    @app.route('/whatsapp/nagranie/<int:bid>')
    def whatsapp_audio(bid):
        W.bind(s)
        with contextlib.closing(W.db()) as con:
            b = con.execute('SELECT audio FROM briefs WHERE id=?', (bid,)).fetchone()
        if not b or not b['audio']:
            abort(404)
        path = Path(b['audio'])
        if not path.exists() or W.home() not in path.resolve().parents:
            abort(404)
        return send_file(path, mimetype='audio/wav')
