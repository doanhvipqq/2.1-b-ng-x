import requests
import json
import time
import os
import sys
import threading
from utils import get_random_user_agent

class InstagramAutomation:
    def __init__(self):
        self.ses = requests.Session()
        self.golike_headers = None
        self.telegram_callback = None
        self.stop_event = threading.Event()
        
    def stop(self):
        """Dừng automation"""
        self.stop_event.set()
        
    def get_accounts(self, auth_token, t_header):
        """
        Get Instagram accounts from Golike
        """
        try:
            auth_token = auth_token.strip()
            t_header = t_header.strip()
            
            # Use same user agent logic as AutoIG.py
            user_agent = get_random_user_agent()
            
            def make_request(token, t):
                headers = {
                    'Accept-Language': 'vi,en-US;q=0.9,en;q=0.8',
                    'Referer': 'https://app.golike.net/',
                    'Sec-Ch-Ua': '"Not A(Brand";v="99", "Google Chrome";v="121", "Chromium";v="121"',
                    'Sec-Ch-Ua-Mobile': '?0',
                    'Sec-Ch-Ua-Platform': 'Windows',
                    'Sec-Fetch-Dest': 'empty',
                    'Sec-Fetch-Mode': 'cors',
                    'Sec-Fetch-Site': 'same-site',
                    'T': t,
                    'User-Agent': user_agent,
                    'Authorization': token,
                    'Content-Type': 'application/json;charset=utf-8'
                }
                url = 'https://gateway.golike.net/api/instagram-account'
                try:
                    resp = self.ses.get(url, headers=headers, timeout=10)
                    return resp
                except Exception as e:
                    print(f'[ERROR] Request failed: {e}')
                    return None

            print('[*] Connecting to Golike...')
            sys.stdout.flush()

            # Try 1: As provided
            resp = make_request(auth_token, t_header)
            
            # Try 2: If 401/500, try adding Bearer prefix if missing
            if resp is None or resp.status_code in [401, 500]:
                if not auth_token.startswith('Bearer '):
                    print('[*] Retrying with Bearer prefix...')
                    resp = make_request(f'Bearer {auth_token}', t_header)

            # Try 3: If still 401/500, try cleaning User-Agent (remove android| prefix)
            if resp is None or resp.status_code in [401, 500]:
                if '|' in user_agent:
                    print('[*] Retrying with clean User-Agent...')
                    user_agent = user_agent.split('|')[1]
                    resp = make_request(auth_token, t_header)
                    if resp is None or resp.status_code in [401, 500]:
                        if not auth_token.startswith('Bearer '):
                            resp = make_request(f'Bearer {auth_token}', t_header)

            if resp is None:
                return None

            print(f'[DEBUG] HTTP Status: {resp.status_code}')
            sys.stdout.flush()
            
            try:
                response = resp.json()
                print(f'[DEBUG] API Response: {json.dumps(response)[:100]}...')
                sys.stdout.flush()
            except:
                print(f'[DEBUG] Raw Response: {resp.text[:100]}')
                sys.stdout.flush()
                return None
                
            status = response.get('status')
            print(f'[DEBUG] API Status: {status}')
            sys.stdout.flush()
            
            if status == 200:
                accounts = []
                for data in response['data']:
                    accounts.append({
                        'id': data['id'],
                        'username': data['instagram_username'],
                        'unique_username': data['username']
                    })
                print(f'[+] Found {len(accounts)} accounts')
                sys.stdout.flush()
                return accounts
            else:
                # Show error message
                error_msg = response.get('message', 'Unknown error')
                safe_msg = ''.join(c if ord(c) < 128 else '?' for c in str(error_msg))
                print(f'[ERROR] Golike error: {safe_msg}')
                sys.stdout.flush()
                return None
                
        except Exception as e:
            error_str = str(e)[:200]
            safe_error = ''.join(c if ord(c) < 128 else '?' for c in error_str)
            print(f'[ERROR] Exception: {safe_error}')
            sys.stdout.flush()
            return None
    
    def solve_job(self, account, cookie, delay, num_jobs=None):
        account_id = account['id']
        username = account.get('username', 'automation')
        completed_jobs = 0
        failed_jobs = 0
        total_earned = 0
        start_time = time.time()
        
        def gs(s, l=1024): 
            """Giữ nguyên Unicode cho Telegram, chỉ lọc ASCII cho console nếu cần - nhưng hiện tại đa số console đã hỗ trợ UTF-8"""
            if s is None: return ""
            return str(s)[:l]
            
        def safe_log(s):
            """Hàm log an toàn cho console Windows (gbk)"""
            print(''.join(c if ord(c) < 128 else '?' for c in str(s)))
            sys.stdout.flush()

        print(f'[+] Running: {username}')
        if num_jobs:
            print(f'[*] Target: {num_jobs} jobs')
        sys.stdout.flush()
        
        try:
            csrftoken = cookie.split('csrftoken=')[1].split(';')[0]
        except:
            safe_log('[ERROR] No csrftoken in cookie!')
            return
        
        # Instagram headers from AutoIG.py
        headerINS = {
            'accept': '*/*',
            'accept-language': 'vi,en-US;q=0.9,en;q=0.8',
            'content-type': 'application/x-www-form-urlencoded',
            'cookie': cookie,
            'origin': 'https://www.instagram.com',
            'priority': 'u=1, i',
            'referer': 'https://www.instagram.com/p/C9RAZEJNjPC/',
            'sec-ch-prefers-color-scheme': 'dark',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin',
            'user-agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1',
            'x-asbd-id': '129477',
            'x-csrftoken': csrftoken,
            'x-ig-app-id': '936619743392459',
            'x-ig-www-claim': 'hmac.AR1Jw2LrciyrzAQskwSVGREElPZZJZjW74y38oTjDnNHOu9e',
            'x-instagram-ajax': '1014868636',
            'x-requested-with': 'XMLHttpRequest',
        }
        
        param = {
            'instagram_account_id': account_id,
            'data': 'null',
        }
        
        while not self.stop_event.is_set():
            if num_jobs and completed_jobs >= num_jobs:
                elapsed = int(time.time() - start_time)
                summary = (
                    '='*60 + '\n' +
                    '[SUCCESS] COMPLETED!\n' +
                    '='*60 + '\n' +
                    f'Account: @{username}\n' +
                    f'[+] Completed: {completed_jobs}\n' +
                    f'[-] Failed: {failed_jobs}\n' +
                    f'[$] Earned: {total_earned}d\n' +
                    f'[T] Time: {elapsed}s\n' +
                    '='*60
                )
                print(summary)
                sys.stdout.flush()
                
                if self.telegram_callback:
                    self.telegram_callback(f'Hoan thanh {completed_jobs} jobs! Thu nhap: {total_earned}d', {
                        'completed_jobs': completed_jobs,
                        'total_jobs': num_jobs,
                        'total_earned': total_earned,
                        'failed_jobs': failed_jobs
                    })
                
                break
            
            try:
                # Match AutoIG.py format exactly - query string in URL
                job_url = f'https://gateway.golike.net/api/advertising/publishers/instagram/jobs?instagram_account_id={account_id}&data=null'
                nos = self.ses.get(job_url, headers=self.golike_headers).json()
                
                if nos['status'] == 200:
                    ads_id = nos['data']['id']
                    object_id = nos['data']['object_id']
                    job_type = nos['data']['type']
                    link = nos['data']['link']
                    
                    job_num = completed_jobs + 1
                    print(f'[*] Job {job_num}/{num_jobs if num_jobs else "?"}: {job_type}')
                    sys.stdout.flush()
                    
                    if self.telegram_callback:
                        stats = {
                            'completed_jobs': completed_jobs,
                            'failed_jobs': failed_jobs,
                            'total_earned': total_earned,
                            'total_jobs': num_jobs,
                            'ads_id': ads_id,
                            'job_type': job_type,
                            'job_num': job_num
                        }
                        self.telegram_callback(f'Bắt đầu job: {job_type}', stats)
                    
                    # Redirect check (similar to AutoIG.py)
                    try:
                        check_resp = requests.get(link, headers={'User-Agent': headerINS['user-agent']}, timeout=10, allow_redirects=True)
                        if check_resp.status_code == 404:
                            safe_log(f'[!] Job link 404, skipping...')
                            self.skip_job(ads_id, account_id, object_id, job_type, completed_jobs, failed_jobs, total_earned, num_jobs)
                            if self.telegram_callback:
                                stats = {
                                    'completed_jobs': completed_jobs,
                                    'failed_jobs': failed_jobs + 1,
                                    'total_earned': total_earned,
                                    'total_jobs': num_jobs,
                                    'ads_id': ads_id,
                                    'job_type': job_type,
                                    'job_num': job_num
                                }
                                self.telegram_callback(f'Link lỗi 404 (Job đã bị xóa)', stats)
                            failed_jobs += 1
                            continue
                    except: pass

                    if job_type == 'follow':
                        url = f'https://www.instagram.com/api/v1/friendships/create/{object_id}/'
                        data = {
                            'container_module': 'profile',
                            'nav_chain': 'PolarisFeedRoot:feedPage:8:topnav-link',
                            'user_id': object_id,
                        }
                        
                        try:
                            resp_obj = requests.post(url, headers=headerINS, data=data, timeout=10)
                            response = resp_obj.text
                        except Exception as e:
                            print(f'[ERROR] Instagram request failed: {gs(e)}')
                            response = ''
                            
                        self.countdown(delay)
                        if self.stop_event.is_set(): break
                        
                        if '"status":"ok"' in response:
                            earned, err_msg = self.complete_job(account_id, ads_id)
                            if earned:
                                completed_jobs += 1
                                total_earned += earned
                                if self.telegram_callback:
                                    stats = {
                                        'completed_jobs': completed_jobs,
                                        'failed_jobs': failed_jobs,
                                        'total_earned': total_earned,
                                        'total_jobs': num_jobs,
                                        'ads_id': ads_id,
                                        'job_type': job_type,
                                        'job_num': job_num
                                    }
                                    self.telegram_callback(f'Follow OK +{earned}d', stats)
                            else:
                                if self.telegram_callback:
                                    stats = {
                                        'completed_jobs': completed_jobs,
                                        'failed_jobs': failed_jobs + 1,
                                        'total_earned': total_earned,
                                        'total_jobs': num_jobs,
                                        'ads_id': ads_id,
                                        'job_type': job_type,
                                        'job_num': job_num
                                    }
                                    self.telegram_callback(f'Lỗi hoàn thành: {err_msg}', stats)
                                self.skip_job(ads_id, account_id, object_id, job_type, completed_jobs, failed_jobs, total_earned, num_jobs)
                                failed_jobs += 1
                                
                        elif '"status":"fail"' in response and '"spam":true' in response:
                            print('[!] Spam blocked')
                            sys.stdout.flush()
                            if self.telegram_callback:
                                stats = {
                                    'completed_jobs': completed_jobs,
                                    'failed_jobs': failed_jobs + 1,
                                    'total_earned': total_earned,
                                    'total_jobs': num_jobs,
                                    'ads_id': ads_id,
                                    'job_type': job_type,
                                    'job_num': job_num
                                }
                                self.telegram_callback(f'Lỗi: Instagram báo SPAM (Chặn Profile)', stats)
                            self.skip_job(ads_id, account_id, object_id, job_type, completed_jobs, failed_jobs, total_earned, num_jobs)
                            failed_jobs += 1
                        elif '"status":"fail"' in response and '"require_login":true' in response:
                            print('[!] Cookie expired')
                            sys.stdout.flush()
                            if self.telegram_callback:
                                stats = {
                                    'completed_jobs': completed_jobs,
                                    'failed_jobs': failed_jobs,
                                    'total_earned': total_earned,
                                    'total_jobs': num_jobs,
                                    'ads_id': ads_id,
                                    'job_type': job_type,
                                    'job_num': job_num
                                }
                                self.telegram_callback('Lỗi: Cookie Instagram đã hết hạn!', stats)
                            break
                        else:
                            detail = ""
                            if '<html' in response.lower() or '<!doctype' in response.lower():
                                detail = "Instagram trả về trang HTML (Yêu cầu đăng nhập hoặc bot check)"
                            else:
                                detail = gs(response, 100)
                            
                            sys.stdout.flush()
                            if self.telegram_callback:
                                stats = {
                                    'completed_jobs': completed_jobs,
                                    'failed_jobs': failed_jobs + 1,
                                    'total_earned': total_earned,
                                    'total_jobs': num_jobs,
                                    'ads_id': ads_id,
                                    'job_type': job_type,
                                    'job_num': job_num
                                }
                                self.telegram_callback(f'Lỗi Instagram: {detail}', stats)
                            
                            self.skip_job(ads_id, account_id, object_id, job_type, completed_jobs, failed_jobs, total_earned, num_jobs)
                            failed_jobs += 1
                    
                    elif job_type == 'like':
                        try:
                            like_id = nos['data']['description']
                        except:
                            like_id = object_id
                        
                        url = f'https://www.instagram.com/api/v1/web/likes/{like_id}/like/'
                        
                        try:
                            resp_obj = requests.post(url, headers=headerINS, timeout=10)
                            response = resp_obj.text
                        except Exception as e:
                            print(f'[ERROR] Instagram request failed: {gs(e)}')
                            response = ''
                            
                        self.countdown(delay)
                        if self.stop_event.is_set(): break
                        
                        if '"status":"ok"' in response:
                            earned, err_msg = self.complete_job(account_id, ads_id)
                            if earned:
                                completed_jobs += 1
                                total_earned += earned
                                if self.telegram_callback:
                                    stats = {
                                        'completed_jobs': completed_jobs,
                                        'failed_jobs': failed_jobs,
                                        'total_earned': total_earned,
                                        'total_jobs': num_jobs,
                                        'ads_id': ads_id,
                                        'job_type': job_type,
                                        'job_num': job_num
                                    }
                                    self.telegram_callback(f'Like OK +{earned}d', stats)
                            else:
                                if self.telegram_callback:
                                    stats = {
                                        'completed_jobs': completed_jobs,
                                        'failed_jobs': failed_jobs + 1,
                                        'total_earned': total_earned,
                                        'total_jobs': num_jobs,
                                        'ads_id': ads_id,
                                        'job_type': job_type,
                                        'job_num': job_num
                                    }
                                    self.telegram_callback(f'Lỗi hoàn thành: {err_msg}', stats)
                                self.skip_job(ads_id, account_id, object_id, job_type, completed_jobs, failed_jobs, total_earned, num_jobs)
                                failed_jobs += 1
                        elif '"status":"fail"' in response and '"spam":true' in response:
                            print('[!] Spam blocked')
                            sys.stdout.flush()
                            if self.telegram_callback:
                                stats = {
                                    'completed_jobs': completed_jobs,
                                    'failed_jobs': failed_jobs + 1,
                                    'total_earned': total_earned,
                                    'total_jobs': num_jobs,
                                    'ads_id': ads_id,
                                    'job_type': job_type,
                                    'job_num': job_num
                                }
                                self.telegram_callback(f'Lỗi: Instagram chặn LIKE bài viết này', stats)
                            self.skip_job(ads_id, account_id, object_id, job_type, completed_jobs, failed_jobs, total_earned, num_jobs)
                            failed_jobs += 1
                        elif '"status":"fail"' in response and '"require_login":true' in response:
                            print('[!] Cookie expired')
                            sys.stdout.flush()
                            if self.telegram_callback:
                                stats = {
                                    'completed_jobs': completed_jobs,
                                    'failed_jobs': failed_jobs,
                                    'total_earned': total_earned,
                                    'total_jobs': num_jobs,
                                    'ads_id': ads_id,
                                    'job_type': job_type,
                                    'job_num': job_num
                                }
                                self.telegram_callback('Lỗi: Cookie Instagram đã hết hạn!', stats)
                            break
                        else:
                            detail = ""
                            if '<html' in response.lower() or '<!doctype' in response.lower():
                                detail = "Instagram trả về trang HTML (Yêu cầu đăng nhập hoặc bot check)"
                            else:
                                detail = gs(response, 100)
                                
                            sys.stdout.flush()
                            if self.telegram_callback:
                                stats = {
                                    'completed_jobs': completed_jobs,
                                    'failed_jobs': failed_jobs + 1,
                                    'total_earned': total_earned,
                                    'total_jobs': num_jobs,
                                    'ads_id': ads_id,
                                    'job_type': job_type,
                                    'job_num': job_num
                                }
                                self.telegram_callback(f'Lỗi Instagram: {detail}', stats)
                            
                            self.skip_job(ads_id, account_id, object_id, job_type, completed_jobs, failed_jobs, total_earned, num_jobs)
                            failed_jobs += 1
                    
                    elif job_type == 'comment':
                        print(f'[*] Job type "comment" not supported yet, skipping...')
                        sys.stdout.flush()
                        if self.telegram_callback:
                            stats = {
                                'completed_jobs': completed_jobs,
                                'failed_jobs': failed_jobs,
                                'total_earned': total_earned,
                                'total_jobs': num_jobs,
                                'ads_id': ads_id,
                                'job_type': job_type,
                                'job_num': job_num
                            }
                            self.telegram_callback('Bỏ qua job Comment (chưa hỗ trợ)', stats)
                        self.skip_job(ads_id, account_id, object_id, job_type, completed_jobs, failed_jobs, total_earned, num_jobs)
                    
                    else:
                        safe_log(f'[!] Job type "{job_type}" not supported, skipping...')
                        self.skip_job(ads_id, account_id, object_id, job_type, completed_jobs, failed_jobs, total_earned, num_jobs)
                else:
                    msg = nos.get('message', 'Hết Job')
                    safe_log(f'[!] {msg}')
                    if self.telegram_callback:
                        stats = {
                            'completed_jobs': completed_jobs,
                            'failed_jobs': failed_jobs,
                            'total_earned': total_earned,
                            'total_jobs': num_jobs
                        }
                        self.telegram_callback(msg, stats)
                    self.countdown(15)
            
            except Exception as e:
                safe_log(f'[ERROR] {str(e)}')
                # Use wait for interruptible sleep
                self.stop_event.wait(5)
        
        safe_log(f'[*] Instagram Automation stopped.')
    
    def complete_job(self, account_id, ads_id):
        url = 'https://gateway.golike.net/api/advertising/publishers/instagram/complete-jobs'
        json_data = {
            'instagram_account_id': account_id,
            'instagram_users_advertising_id': ads_id,
            'async': True,
            'data': 'null',
        }
        
        # Match AutoIG.py: sleep 3s first for propagation
        time.sleep(3)
        if self.stop_event.is_set(): return 0, "Dừng tool"
        
        try:
            # Attempt 1
            resp = self.ses.post(url, headers=self.golike_headers, json=json_data)
            response = resp.json()
            if response.get('success') == True:
                price = response['data']['prices']
                print(f'[+] Success! +{price}d')
                sys.stdout.flush()
                return price, ""
            else:
                msg = response.get("message", "Unknown error")
                print(f'[!] Check 1 failed: {"".join(c if ord(c) < 128 else "?" for c in str(msg))}. Wait 7s...')
                sys.stdout.flush()
                self.stop_event.wait(7)
                if self.stop_event.is_set(): return 0, "Dừng tool"
                
                # Attempt 2
                resp = self.ses.post(url, headers=self.golike_headers, json=json_data)
                response = resp.json()
                if response.get('success') == True:
                    price = response['data']['prices']
                    print(f'[+] Success after retry! +{price}d')
                    sys.stdout.flush()
                    return price, ""
                else:
                    msg = response.get("message", "Unknown error")
                    safe_msg = ''.join(c if ord(c) < 128 else '?' for c in str(msg))
                    print(f'[!] Final Check failed: {safe_msg}')
                    sys.stdout.flush()
                    return 0, safe_msg
        except Exception as e:
            print(f'[ERROR] Complete: {"".join(c if ord(c) < 128 else "?" for c in str(e)[:100])}')
            sys.stdout.flush()
            return 0, str(e)
    
    def skip_job(self, ads_id, account_id, object_id, job_type, completed_jobs=0, failed_jobs=0, total_earned=0, num_jobs=0):
        # Match AutoIG.py format
        skipjob = 'https://gateway.golike.net/api/advertising/publishers/instagram/skip-jobs'
        params = {
            'ads_id': ads_id,
            'account_id': account_id,
            'object_id': object_id,
            'async': 'true',
            'data': 'null',
            'type': job_type,
        }
        
        try:
            resp = self.ses.post(skipjob, params=params, headers=self.golike_headers)
            status = resp.status_code
            try:
                resp_json = resp.json()
            except:
                resp_json = {"message": "Could not parse JSON"}
                
            if status == 200:
                print(f'[+] Success Skip (Status: {status})')
            else:
                msg = resp_json.get("message", "Unknown error")
                safe_msg = ''.join(c if ord(c) < 128 else '?' for c in str(msg))
                print(f'[!] Skip Failed (Status: {status}): {safe_msg}')
                if status == 422:
                    print(f'[DEBUG] Skip 422 Payload: {params}')
            sys.stdout.flush()
        except Exception as e:
            safe_error = ''.join(c if ord(c) < 128 else '?' for c in str(e))
            print(f'[ERROR] skip_job: {safe_error}')
            sys.stdout.flush()
        
        wait_time = 5 if job_type not in ['follow', 'like'] else 15
        self.countdown(wait_time)
    
    def countdown(self, t):
        print(f'[...] Wait {t}s')
        sys.stdout.flush()
        self.stop_event.wait(t)
    
    def setup(self, auth_token, t_header, account_id, cookie):
        user_agent = get_random_user_agent()
        self.golike_headers = {
            'Accept-Language': 'vi,en-US;q=0.9,en;q=0.8',
            'Referer': 'https://app.golike.net/',
            'Sec-Ch-Ua': '"Not A(Brand";v="99", "Google Chrome";v="121", "Chromium";v="121"',
            'Sec-Ch-Ua-Mobile': '?0',
            'Sec-Ch-Ua-Platform': 'Windows',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-site',
            'T': t_header,
            'User-Agent': user_agent,
            'Authorization': auth_token,
            'Content-Type': 'application/json;charset=utf-8'
        }
        self.account_id = account_id
        self.cookie = cookie
    
    def run(self, num_jobs, delay, progress_callback=None):
        self.telegram_callback = progress_callback
        account = {
            'id': self.account_id,
            'username': 'automation'
        }
        self.solve_job(account, self.cookie, delay, num_jobs)