import requests
import time
import os
import random
import json
import sys
import threading
from utils import get_random_user_agent

class LinkedInAutomation:
    def __init__(self):
        self.ses = requests.Session()
        self.golike_headers = None
        self.telegram_callback = None
        self.stop_event = threading.Event()
        self.account_id = None
        self.cookie = None
    
    def stop(self):
        """Dừng automation"""
        self.stop_event.set()
        
    def get_accounts(self, auth_token, t_header):
        """
        Lấy danh sách tài khoản LinkedIn từ Golike
        """
        try:
            auth_token = auth_token.strip()
            t_header = t_header.strip()
            
            user_agent = get_random_user_agent()
            
            def make_request(token, t):
                headers = {
                    'Accept-Language': 'vi,en-US;q=0.9,en;q=0.8',
                    'Referer': 'https://app.golike.net/',
                    'Sec-Ch-Ua': '"Not A(Brand";v="99", "Google Chrome";v="121", "Chromium";v="121"',
                    'Sec-Ch-Ua-Mobile': '?0',
                    'Sec-Ch-Ua-Platform': "Windows",
                    'Sec-Fetch-Dest': 'empty',
                    'Sec-Fetch-Mode': 'cors',
                    'Sec-Fetch-Site': 'same-site',
                    'T': t,
                    'User-Agent': user_agent,
                    'Authorization': token,
                    'Content-Type': 'application/json;charset=utf-8'
                }
                url = 'https://gateway.golike.net/api/linkedin-account'
                try:
                    resp = self.ses.get(url, headers=headers, timeout=10)
                    return resp
                except Exception as e:
                    return None

            resp = make_request(auth_token, t_header)
            if resp is None or resp.status_code in [401, 500]:
                if not auth_token.startswith('Bearer '):
                    resp = make_request(f'Bearer {auth_token}', t_header)

            if resp is None: return None
            
            try:
                response = resp.json()
            except:
                return None
                
            if response.get('status') == 200:
                accounts = []
                for data in response['data']:
                    accounts.append({
                        'id': data['id'],
                        'username': data['name'],
                        'unique_username': data['name']
                    })
                return accounts
            else:
                return None
            
        except Exception as e:
            return None

    def setup(self, auth_token, t_header, account_id, cookie):
        user_agent = get_random_user_agent()
        self.golike_headers = {
            'Accept-Language': 'vi,en-US;q=0.9,en;q=0.8',
            'Referer': 'https://app.golike.net/',
            'T': t_header,
            'User-Agent': user_agent,
            'Authorization': auth_token,
            'Content-Type': 'application/json;charset=utf-8'
        }
        self.account_id = account_id
        self.cookie = cookie

    def solve_job(self, account_id, cookie, job_limit, delay):
        """
        Thực hiện auto jobs LinkedIn - Based on GolikeLinkedin.py original code
        """
        def safe_log(s):
            print(''.join(c if ord(c) < 128 else '?' for c in str(s)))
            sys.stdout.flush()

        # Extract CSRF token from cookie
        try:
            if 'JSESSIONID="' in cookie:
                csrf_token = cookie.split('JSESSIONID="')[1].split('"')[0]
            elif 'JSESSIONID=' in cookie:
                csrf_token = cookie.split('JSESSIONID=')[1].split(';')[0]
            else:
                csrf_token = cookie.split('JSESSIONID')[1].split(';')[0].replace('=', '').replace('"', '')
        except Exception:
             if self.telegram_callback:
                self.telegram_callback('❌ Cookie lỗi! Không tìm thấy JSESSIONID.', {'completed_jobs': 0, 'total_earned': 0, 'failed_jobs': 0, 'total_jobs': job_limit})
             return

        url_get_job = "https://gateway.golike.net/api/advertising/publishers/linkedin/jobs"
        
        dem = 0
        failed = 0
        tong = 0
        
        while dem < job_limit and not self.stop_event.is_set():
            try:
                # 1. Get Job
                params = {
                    "account_id": account_id,
                    "data": "null"
                }
                res = self.ses.get(url_get_job, headers=self.golike_headers, params=params).json()
                
                if res.get('status') == 200:
                    job_data = res['data']
                    ads_id = job_data['id']
                    job_type = job_data['type']
                    link_job = job_data['link']
                    object_id = job_data['object_id']
                    
                    if self.telegram_callback:
                        stats = {
                            'completed_jobs': dem,
                            'failed_jobs': failed,
                            'total_earned': tong,
                            'total_jobs': job_limit,
                            'ads_id': ads_id,
                            'job_type': job_type,
                            'job_num': dem + 1
                        }
                        self.telegram_callback(f'Bắt đầu job: {job_type}', stats)
                    
                    # Wait delay before processing
                    self.stop_event.wait(delay)
                    if self.stop_event.is_set(): break
                    
                    # 2. Process Job
                    if job_type == 'follow':
                        # Get page to extract entity URN
                        haeaders = {
                            'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
                            'accept-language': 'vi,en-US;q=0.9,en;q=0.8',
                            'cache-control': 'max-age=0',
                            'cookie': cookie,
                            'referer': 'https://app.golike.net/',
                            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
                        }
                        
                        # Fix potential wrong domain in link_job
                        link_job = link_job.replace('www.in.linkedin.com', 'www.linkedin.com')
                        link_job = link_job.replace('http://', 'https://')
                        
                        try:
                            response = requests.get(link_job, headers=haeaders, timeout=10).text
                        except Exception as req_err:
                            safe_log(f'[ERROR] Request failed: {req_err}')
                            # If request fails, try to complete job anyway
                            response = ""
                        
                        # Check if profile/company exists in page
                        has_entity = 'li:fsd_company' in response or 'identityDashProfilesByMemberIdentity&quot;:{&quot;*elements&quot;:[&quot;urn:li:fsd_profile:' in response
                        
                        if not has_entity:
                            # No entity found, complete job anyway
                            json_data2 = {
                                'account_id': account_id,
                                'ads_id': ads_id,
                            }
                            url = 'https://gateway.golike.net/api/advertising/publishers/linkedin/complete-jobs'
                            check = requests.post(url, headers=self.golike_headers, json=json_data2).json()
                           
                            if check.get('success') == True:
                                dem += 1
                                prices = check['data']['prices']
                                tong += prices
                                safe_log(f'[+] LinkedIn Success! +{prices}d')
                                if self.telegram_callback:
                                    stats = {
                                        'completed_jobs': dem,
                                        'failed_jobs': failed,
                                        'total_earned': tong,
                                        'total_jobs': job_limit,
                                        'ads_id': ads_id,
                                        'job_type': job_type,
                                        'job_num': dem
                                    }
                                    self.telegram_callback(f'{job_type.capitalize()} OK +{prices}d', stats)
                            else:
                                # Skip job if complete failed
                                self._skip_job(ads_id, account_id, object_id, dem, failed, tong, job_limit, job_type)
                                failed += 1
                        else:
                            # Entity found, perform follow action
                            json_data = {
                                'patch': {
                                    '$set': {
                                        'following': True,
                                    },
                                },
                            }
                            
                            ID = None
                            is_company = False
                            
                            # Extract ID - try company first
                            if 'li:fsd_company:' in response:
                                try:
                                    ID = response.split('li:fsd_company:')[1].split('&')[0]
                                    is_company = True
                                except: pass
                                
                            # If not company, try profile
                            if not ID and 'identityDashProfilesByMemberIdentity&quot;:{&quot;*elements&quot;:[&quot;urn:li:fsd_profile:' in response:
                                try:
                                    ID = response.split('identityDashProfilesByMemberIdentity&quot;:{&quot;*elements&quot;:[&quot;urn:li:fsd_profile:')[1].split('&')[0]
                                    is_company = False
                                except: pass
                            
                            if ID:
                                # Prepare headers based on type
                                if is_company:
                                    headers_api = {
                                        'accept': 'application/vnd.linkedin.normalized+json+2.1',
                                        'accept-language': 'vi,en-US;q=0.9,en;q=0.8',
                                        'content-type': 'application/json; charset=UTF-8',
                                        'cookie': cookie,
                                        'csrf-token': csrf_token,
                                        'origin': 'https://www.linkedin.com',
                                        'referer': 'https://www.linkedin.com/company/chatplayground-ai/posts/?feedView=all',
                                        'user-agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1',
                                        'x-li-lang': 'en_US',
                                        'x-li-page-instance': 'urn:li:page:companies_company_posts_index;7952eddd-435c-428e-9587-a2dd19a42e2f',
                                        'x-li-pem-metadata': 'Voyager - Organization - Member=organization-follow',
                                        'x-li-track': '{"clientVersion":"1.13.19938","mpVersion":"1.13.19938","osName":"web","timezoneOffset":7,"timezone":"Asia/Bangkok","deviceFormFactor":"DESKTOP","mpName":"voyager-web","displayDensity":1.5625,"displayWidth":2400,"displayHeight":1350}',
                                        'x-restli-protocol-version': '2.0.0',
                                    }
                                    entity_urn = f"urn:li:fsd_company:{ID}"
                                else:
                                    headers_api = {
                                        'accept': 'application/vnd.linkedin.normalized+json+2.1',
                                        'accept-language': 'vi,en-US;q=0.9,en;q=0.8',
                                        'content-type': 'application/json; charset=UTF-8',
                                        'cookie': cookie,
                                        'csrf-token': csrf_token,
                                        'origin': 'https://www.linkedin.com',
                                        'referer': 'https://www.linkedin.com/in/noman-chaudhary-52031148/',
                                        'user-agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1',
                                        'x-li-lang': 'en_US',
                                        'x-li-page-instance': 'urn:li:page:d_flagship3_profile_view_base;I6RhpcMURWuRvBmeIhl5BQ==',
                                        'x-li-pem-metadata': 'Voyager - Follows=follow-action,Voyager - Profile Actions=topcard-primary-follow-action-click',
                                        'x-li-track': '{"clientVersion":"1.13.19938","mpVersion":"1.13.19938","osName":"web","timezoneOffset":7,"timezone":"Asia/Bangkok","deviceFormFactor":"DESKTOP","mpName":"voyager-web","displayDensity":1.5625,"displayWidth":2400,"displayHeight":1350}',
                                        'x-restli-protocol-version': '2.0.0',
                                    }
                                    entity_urn = f"urn:li:fsd_profile:{ID}"
                                
                                # Perform follow
                                requests.post(
                                    f'https://www.linkedin.com/voyager/api/feed/dash/followingStates/urn:li:fsd_followingState:{entity_urn}',
                                    headers=headers_api,
                                    json=json_data
                                )
                                time.sleep(2)
                            
                            # Complete job
                            json_data2 = {
                                'account_id': account_id,
                                'ads_id': ads_id,
                            }
                            url = 'https://gateway.golike.net/api/advertising/publishers/linkedin/complete-jobs'
                            check = requests.post(url, headers=self.golike_headers, json=json_data2).json()
                            
                            if check.get('success') == True:
                                dem += 1
                                prices = check['data']['prices']
                                tong += prices
                                safe_log(f'[+] LinkedIn Success! +{prices}d')
                                if self.telegram_callback:
                                    stats = {
                                        'completed_jobs': dem,
                                        'failed_jobs': failed,
                                        'total_earned': tong,
                                        'total_jobs': job_limit,
                                        'ads_id': ads_id,
                                        'job_type': job_type,
                                        'job_num': dem
                                    }
                                    self.telegram_callback(f'{job_type.capitalize()} OK +{prices}d', stats)
                            else:
                                self._skip_job(ads_id, account_id, object_id, dem, failed, tong, job_limit, job_type)
                                failed += 1
                    
                    elif job_type == 'like':
                        # LinkedIn like job
                        headers_like = {
                            'accept': 'application/vnd.linkedin.normalized+json+2.1',
                            'accept-language': 'vi,en-US;q=0.9,en;q=0.8',
                            'content-type': 'application/json; charset=UTF-8',
                            'cookie': cookie,
                            'csrf-token': csrf_token,
                            'origin': 'https://www.linkedin.com',
                            'referer': 'https://www.linkedin.com/feed/update/urn:li:activity:7219700822467575808/',
                            'user-agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1',
                            'x-li-lang': 'en_US',
                            'x-li-track': '{"clientVersion":"1.13.20142","mpVersion":"1.13.20142","osName":"web","timezoneOffset":7,"timezone":"Asia/Bangkok","deviceFormFactor":"DESKTOP","mpName":"voyager-web","displayDensity":1.5625,"displayWidth":2400,"displayHeight":1350}',
                            'x-restli-protocol-version': '2.0.0',
                        }
                        
                        params = {
                            'action': 'execute',
                            'queryId': 'voyagerSocialDashReactions.b731222600772fd42464c0fe19bd722b',
                        }
                        
                        json_data = {
                            'variables': {
                                'entity': {
                                    'reactionType': 'LIKE',
                                },
                                'threadUrn': 'urn:li:activity:' + str(object_id),
                            },
                            'queryId': 'voyagerSocialDashReactions.b731222600772fd42464c0fe19bd722b',
                            'includeWebMetadata': True,
                        }
                        
                        requests.post(
                            'https://www.linkedin.com/voyager/api/graphql',
                            params=params,
                            headers=headers_like,
                            json=json_data
                        )
                        time.sleep(2)
                        
                        # Complete job
                        json_data2 = {
                            'account_id': account_id,
                            'ads_id': ads_id,
                        }
                        url = 'https://gateway.golike.net/api/advertising/publishers/linkedin/complete-jobs'
                        check = requests.post(url, headers=self.golike_headers, json=json_data2).json()
                        
                        if check.get('success') == True:
                            dem += 1
                            prices = check['data']['prices']
                            tong += prices
                            safe_log(f'[+] LinkedIn Success! +{prices}d')
                            if self.telegram_callback:
                                stats = {
                                    'completed_jobs': dem,
                                    'failed_jobs': failed,
                                    'total_earned': tong,
                                    'total_jobs': job_limit,
                                    'ads_id': ads_id,
                                    'job_type': job_type,
                                    'job_num': dem
                                }
                                self.telegram_callback(f'{job_type.capitalize()} OK +{prices}d', stats)
                        else:
                            self._skip_job(ads_id, account_id, object_id, dem, failed, tong, job_limit, job_type)
                            failed += 1
                            
                else:
                    msg = res.get("message", "Đang hết job hoặc tài khoản bị hạn chế")
                    msg_lower = msg.lower()
                    if "lock" in msg_lower or "ban" in msg_lower or "restrict" in msg_lower:
                        msg = "⚠️ Tài khoản LinkedIn bị khóa hoặc giới hạn!"
                    elif "limit" in msg_lower or "rate" in msg_lower:
                        msg = "⚠️ Đã vượt giới hạn, vui lòng chờ!"
                    
                    safe_log(f'[!] LinkedIn: {msg}')
                    if self.telegram_callback:
                        stats = {
                            'completed_jobs': dem,
                            'failed_jobs': failed,
                            'total_earned': tong,
                            'total_jobs': job_limit,
                            'ads_id': 'N/A',
                            'job_type': 'status'
                        }
                        self.telegram_callback(msg, stats)
                    self.stop_event.wait(15)
                    
            except Exception as e:
                safe_log(f'[ERROR] LinkedIn execution: {str(e)}')
                self.stop_event.wait(5)
                
        safe_log(f'[*] LinkedIn Automation stopped.')
        if self.telegram_callback:
            stats = {
                'completed_jobs': dem,
                'failed_jobs': failed,
                'total_earned': tong,
                'total_jobs': job_limit
            }
            if self.stop_event.is_set():
                self.telegram_callback(f'Đã dừng LinkedIn!', stats)
            else:
                self.telegram_callback(f'Hoàn thành {dem} jobs LinkedIn!', stats)

    def _skip_job(self, ads_id, account_id, object_id, dem, failed, tong, job_limit, job_type):
        """Skip job helper function - based on original code"""
        skipjob = 'https://gateway.golike.net/api/advertising/publishers/linkedin/skip-jobs'
        PARAMS = {
            'ads_id': ads_id,
            'account_id': account_id,
            'object_id': object_id,
        }
        try:
            checkskipjob = self.ses.post(skipjob, params=PARAMS, headers=self.golike_headers).json()
            if checkskipjob.get('status') == 200:
                message = checkskipjob.get('message', 'Skip OK')
                print(f'[SKIP] {message}')
                sys.stdout.flush()
        except:
            pass
        
        if self.telegram_callback:
            stats = {
                'completed_jobs': dem,
                'failed_jobs': failed + 1,
                'total_earned': tong,
                'total_jobs': job_limit,
                'ads_id': ads_id,
                'job_type': job_type,
                'job_num': dem + 1
            }
            self.telegram_callback('Lỗi hoàn thành job, đã skip', stats)

    def run(self, num_jobs, delay, progress_callback=None):
        self.telegram_callback = progress_callback
        if not self.account_id or not self.cookie:
            if self.telegram_callback:
                self.telegram_callback("Chưa setup thông tin Account/Cookie!", {})
            return
        self.solve_job(self.account_id, self.cookie, num_jobs, delay)
