import logging
import asyncio
import os
import sys
import threading
import time
import html
from datetime import datetime
from config import Config

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ConversationHandler
)

from instagram_automation import InstagramAutomation
from linkedin_automation import LinkedInAutomation
from keep_alive import keep_alive

# Cấu hình stdout cho Windows để tránh lỗi Unicode khi in Emoji
try:
    if sys.platform == "win32":
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
except:
    pass

# Cấu hình logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# load_dotenv() # Removed as per user request to use config.py directly

# Trạng thái hội thoại - Clear naming instead of magic numbers
(
    MAIN_MENU,
    # Instagram flow
    IG_AUTH, IG_T_HEADER, IG_SELECT_ACCOUNT, IG_COOKIE, IG_JOBS, IG_DELAY, IG_CONFIRM,
    # LinkedIn flow
    LI_AUTH, LI_T_HEADER, LI_SELECT_ACCOUNT, LI_COOKIE, LI_JOBS, LI_DELAY, LI_CONFIRM
) = range(15)

# Config is now imported from config.py

# Biến toàn cục để lưu trữ các instance automation
instagram_automations = {}
linkedin_automations = {}
automation_threads = {}

# Thống kê chi tiết cho mỗi session
# Format: {user_id: {'ig': {...}, 'li': {...}}}
automation_sessions = {}

# Thông tin user để admin theo dõi
# Format: {user_id: {'username': '@username', 'first_name': 'Name', 'last_active': timestamp}}
user_info = {}


def format_progress_message(platform, message, stats, username):
    """Tạo giao diện báo cáo tiến độ theo yêu cầu người dùng"""
    completed = stats.get('completed_jobs', 0)
    total = stats.get('total_jobs', 0)
    earned = stats.get('total_earned', 0)
    failed = stats.get('failed_jobs', 0)
    ads_id = stats.get('ads_id', 'N/A')
    job_type = stats.get('job_type', 'N/A')
    job_num = stats.get('job_num', completed + 1)
    
    # Xử lý các icon trạng thái
    status_icon = "⏳"
    
    # Ensure message is string and handle safely
    message = str(message) if message else ""
    msg_lower = message.lower()
    
    # Ưu tiên các trạng thái đặc biệt trước
    if "nghỉ" in msg_lower or "chờ" in msg_lower or "giây" in msg_lower or "30p" in msg_lower:
        status_icon = "💤"
    elif "chặn" in msg_lower or "spam" in msg_lower or "block" in msg_lower:
        status_icon = "🛑"
    elif "khóa" in msg_lower or "locked" in msg_lower or "bị chặn" in msg_lower or "hạn chế" in msg_lower:
        status_icon = "🔒"
    elif "hết" in msg_lower or "không có" in msg_lower:
        status_icon = "⏸️"
    elif "ok" in message or "thanh" in msg_lower or "+" in message:
        status_icon = "✅"
    elif "skip" in msg_lower or "bỏ qua" in msg_lower:
        status_icon = "🔄"
    elif "lỗi" in msg_lower or "failed" in msg_lower or "hat bai" in msg_lower:
        status_icon = "⚠️"
        
    # Sanitize for HTML - keep Vietnamese characters
    safe_username = html.escape(str(username))
    safe_message = html.escape(message)
    
    # Trường hợp bắt đầu Job
    if "bắt đầu" in msg_lower or "starting" in msg_lower:
        text = (
            f"⏳ <b>{platform.upper()} - JOB #{job_num}</b>\n"
            f"➕ Loại: <code>{job_type.upper()}</code>\n"
            f"🆔 ID: <code>{ads_id}</code>\n"
            f"⏱️ Đang xử lý..."
        )
    # Trường hợp hoàn thành
    elif "ok" in message or "+" in message:
        plus_earned = ""
        if "+" in message:
            try:
                plus_earned = message.split("+")[1].split("d")[0]
            except: pass
            
        text = (
            f"✅ <b>{platform.upper()} - HOÀN THÀNH</b>\n"
            f"💰 <code>+{plus_earned} VND</code>\n"
            f"📊 Tổng: <code>{completed}</code> | 📱 <code>{safe_username}</code>\n"
            f"💰 Tổng tiền: <code>{earned} VND</code>"
        )
    # Trường hợp lỗi/nghỉ/skip
    else:
        text = (
            f"{status_icon} <b>{platform.upper()} STATUS</b>\n"
            f"🆔 ID: <code>{ads_id}</code>\n"
            f"✍️ {safe_message}\n"
            f"📊 Xong: <code>{completed}</code> (Lỗi: {failed})\n"
            f"📱 <code>{safe_username}</code>\n"
            f"💰 Tổng tiền: <code>{earned} VND</code>"
        )
        
    return text


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handler cho lệnh /start"""
    user = update.effective_user
    logging.info(f"Start command received from user: {user.id} ({user.username})")
    
    # Check authorization - Only block if ALLOWED_USER_IDS is explicitly set and user is not in it
    # If ALLOWED_USER_IDS is None or empty, allow all users
    if Config.ALLOWED_USER_IDS is not None and len(Config.ALLOWED_USER_IDS) > 0 and user.id not in Config.ALLOWED_USER_IDS:
        logging.warning(f"User {user.id} (@{user.username}) not in ALLOWED_USER_IDS - Access denied")
        await update.message.reply_text("⛔ Bạn không có quyền sử dụng bot này!")
        return ConversationHandler.END
    
    # Track user info for admin
    user_info[user.id] = {
        'username': user.username or 'N/A',
        'first_name': user.first_name or 'Unknown',
        'last_active': time.time()
    }
    
    welcome_text = (
        "⚽ <b>BÓNG X</b> ⚽\n\n"
        f"🎯 Chào mừng, <b>{user.first_name}</b>!\n\n"
        "<b>NỀN TẢNG HỖ TRỢ</b>\n\n"
        "📸 <b>Instagram</b>\n"
        "   • Like • Follow • Comment\n\n"
        "💼 <b>LinkedIn</b>\n"
        "   • Like • Follow • Share\n\n"
        "💎 Chọn nền tảng để bắt đầu\n\n"
        "👨‍💻 <b>Trần Đức Doanh</b>\n"
        "🔗 t.me/doanhvip1\n"
        "📞 @doanhvip12"
    )
    
    keyboard = [
        [
            InlineKeyboardButton("📸 Instagram", callback_data='ig'),
            InlineKeyboardButton("💼 LinkedIn", callback_data='li')
        ],
        [
            InlineKeyboardButton("📊 Trạng thái", callback_data='status'),
            InlineKeyboardButton("❓ Hướng dẫn", callback_data='help')
        ]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode='HTML')
    return MAIN_MENU

async def menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Xử lý lựa chọn từ menu chính"""
    query = update.callback_query
    await query.answer()
    
    # Handle back button
    if query.data == 'back':
        # Return to main menu
        user = update.effective_user
        welcome_text = (
            "👑 <b>BÓNG X</b> 👑\n\n"
            f"🎯 Chào mừng, <b>{user.first_name}</b>!\n\n"
            "<b>NỀN TẢNG HỖ TRỢ</b>\n\n"
            "📸 <b>Instagram</b>\n"
            "   • Like • Follow • Comment\n\n"
            "💼 <b>LinkedIn</b>\n"
            "   • Like • Follow • Share\n\n"
            "� <i>Chọn nền tảng bên dưới để bắt đầu</i>\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━\n"
            "👨‍💻 <b>Trần Đức Doanh</b>\n"
            "👑 t.me/doanhvip1 • @doanhvip12\n"
            "━━━━━━━━━━━━━━━━━━━━━━━"
        )
        keyboard = [
            [
                InlineKeyboardButton("📸 Instagram", callback_data='ig'),
                InlineKeyboardButton("💼 LinkedIn", callback_data='li')
            ],
            [
                InlineKeyboardButton("📊 Trạng thái", callback_data='status'),
                InlineKeyboardButton("❓ Hướng dẫn", callback_data='help')
            ]
        ]
        await query.edit_message_text(welcome_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
        return MAIN_MENU
    
    elif query.data == 'help':
        user_id = update.effective_user.id
        is_admin = (user_id == Config.ADMIN_USER_ID)
        
        help_text = (
            "⚡️━━━━━━━━━━━━━━━━━━━━━━⚡️\n"
            "           ⚽ <b>BÓNG X</b> ⚽\n"
            "⚡️━━━━━━━━━━━━━━━━━━━━━━⚡️\n\n"
            "┏━━━ <b>📋 LỆNH CƠ BẢN</b> ━━━┓\n"
            "┃  /start   → Khởi động bot         ┃\n"
            "┃  /help    → Xem hướng dẫn         ┃\n"
            "┃  /status  → Trạng thái hiện tại   ┃\n"
            "┃  /thongke → Xem thống kê chi tiết ┃\n"
            "┃  /stop    → Dừng automation       ┃\n"
            "┃  /reset   → Reset bot              ┃\n"
            "┗━━━━━━━━━━━━━━━━━━━━━━━┛\n\n"
            "┏━━ <b>📊 THỐNG KÊ</b> ━━┓\n"
            "┃  <b>/thongke</b> hoặc <b>/stats</b>     ┃\n"
            "┃                                   ┃\n"
            "┃  • Tốc độ chạy (jobs/phút)       ┃\n"
            "┃  • Tiến độ (%)                   ┃\n"
            "┃  • Thu nhập real-time            ┃\n"
            "┃  • Tỷ lệ thành công              ┃\n"
            "┗━━━━━━━━━━━━━━━━━━━━━━━┛\n\n"
        )
        
        if is_admin:
            help_text += (
                "┏━━ <b>👑 ADMIN PANEL</b> ━━┓\n"
                "┃  <b>/admin</b> - Quản lý hệ thống   ┃\n"
                "┃                                   ┃\n"
                "┃  • Tất cả users đang chạy        ┃\n"
                "┃  • Tốc độ & Hiệu suất            ┃\n"
                "┃  • Tổng thu nhập                 ┃\n"
                "┗━━━━━━━━━━━━━━━━━━━━━━━┛\n\n"
            )
        
        help_text += (
            "┏━━ <b>🔧 HƯỚNG DẪN</b> ━━┓\n"
            "┃                                   ┃\n"
            "┃  1️⃣ Chọn nền tảng (IG/LinkedIn)  ┃\n"
            "┃  2️⃣ Nhập Token + T Header        ┃\n"
            "┃  3️⃣ Chọn tài khoản               ┃\n"
            "┃  4️⃣ Nhập Cookie                  ┃\n"
            "┃  5️⃣ Cấu hình Jobs + Delay        ┃\n"
            "┃  6️⃣ Xác nhận và chạy!            ┃\n"
            "┃                                   ┃\n"
            "┗━━━━━━━━━━━━━━━━━━━━━━━┛\n\n"
            "💡 <b>GỢI Ý:</b>\n"
            "  • Delay ≥ 10s để tránh spam\n"
            "  • Dùng /thongke xem chi tiết\n"
            "  • Token lấy từ Golike\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━\n"
            "👨‍💻 <b>Trần Đức Doanh</b>\n"
            "� t.me/doanhvip1 • @doanhvip12\n"
            "━━━━━━━━━━━━━━━━━━━━━━━"
        )
        keyboard = [[InlineKeyboardButton("🔙 Quay lại", callback_data='back')]]
        await query.edit_message_text(help_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
        return MAIN_MENU
        
    elif query.data == 'ig':
        msg = (
            "📸 <b>INSTAGRAM AUTOMATION</b>\n\n"
            "🔑 Vui lòng nhập <b>Authorization Token</b>\n"
            "từ Golike (bắt đầu với 'Bearer...'):\n\n"
            "💡 <i>Lấy từ tab Network khi dùng Golike</i>"
        )
        keyboard = [[InlineKeyboardButton("🔙 Quay lại", callback_data='back')]]
        await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
        return IG_AUTH
        
    elif query.data == 'li':
        msg = (
            "💼 <b>LINKEDIN AUTOMATION</b>\n\n"
            "🔑 Vui lòng nhập <b>Authorization Token</b>\n"
            "từ Golike LinkedIn:\n\n"
            "💡 <i>Lấy từ tab Network khi dùng Golike</i>"
        )
        keyboard = [[InlineKeyboardButton("🔙 Quay lại", callback_data='back')]]
        await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
        return LI_AUTH
        
    elif query.data == 'status':
        user_id = update.effective_user.id
        msg = "📊 <b>TÌNH TRẠNG AUTOMATION</b>\n\n"
        
        ig_running = user_id in instagram_automations
        li_running = user_id in linkedin_automations
        
        if ig_running:
            msg += "✅ Instagram: <b>Đang chạy</b>\n"
        else:
            msg += "⭕ Instagram: Đang dừng\n"
            
        if li_running:
            msg += "✅ LinkedIn: <b>Đang chạy</b>\n"
        else:
            msg += "⭕ LinkedIn: Đang dừng\n"
        
        msg += "\n💡 Dùng /stop để dừng automation"
        
        # Add quick actions
        keyboard = [
            [InlineKeyboardButton("🔙 Menu chính", callback_data='back')]
        ]
        if ig_running or li_running:
            keyboard.insert(0, [InlineKeyboardButton("🛑 Dừng tất cả", callback_data='stop_all')])
            
        await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
        return MAIN_MENU
    
    elif query.data == 'stop_all':
        user_id = update.effective_user.id
        stopped = False
        
        if user_id in instagram_automations:
            instagram_automations[user_id].stop()
            del instagram_automations[user_id]
            stopped = True
            
        if user_id in linkedin_automations:
            linkedin_automations[user_id].stop()
            del linkedin_automations[user_id]
            stopped = True
        
        if stopped:
            msg = "🛑 <b>Đã dừng tất cả automation!</b>"
        else:
            msg = "⚠️ Không có automation nào đang chạy"
            
        keyboard = [[InlineKeyboardButton("🔙 Menu chính", callback_data='back')]]
        await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='HTML')
        return MAIN_MENU

# --- Instagram Flow ---

async def instagram_auth(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Nhận Authorization token cho Instagram"""
    token = update.message.text.strip()
    
    # Validation: Token should start with Bearer
    if not token.startswith('Bearer'):
        keyboard = [[InlineKeyboardButton("🔙 Quay lại", callback_data='back')]]
        await update.message.reply_text(
            "⚠️ <b>Token không hợp lệ!</b>\n\n"
            "Token phải bắt đầu bằng <code>Bearer...</code>\n\n"
            "💡 <i>Lấy từ tab Network trên Golike</i>",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='HTML'
        )
        return IG_AUTH
    
    context.user_data['ig_token'] = token
    keyboard = [[InlineKeyboardButton("🔙 Quay lại", callback_data='back')]]
    await update.message.reply_text(
        "� <b>Bước 2/5: T Header</b>\n\n"
        "�🔑 Vui lòng nhập <b>T Header</b> cho Instagram:\n\n"
        "💡 <i>Lấy từ tab Network khi dùng Golike</i>",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )
    return IG_T_HEADER

async def instagram_t_header(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Nhận T Header và lấy danh sách tài khoản"""
    context.user_data['ig_t'] = update.message.text.strip()
    
    # Thử lấy danh sách tài khoản
    bot_msg = await update.message.reply_text(
        "⌛ <b>Đang kiểm tra tài khoản...</b>\n\n"
        "🔍 Đang kết nối với Golike...",
        parse_mode='HTML'
    )
    
    try:
        api = InstagramAutomation()
        accounts = api.get_accounts(context.user_data['ig_token'], context.user_data['ig_t'])
        
        if accounts:
            context.user_data['ig_accounts'] = accounts
            msg = "✅ <b>Đã tìm thấy {count} tài khoản Instagram!</b>\n\n".format(count=len(accounts))
            keyboard = []
            for idx, acc in enumerate(accounts, 1):
                msg += f"{idx}️⃣ @{acc['username']}\n"
                keyboard.append([InlineKeyboardButton(
                    f"👉 Chọn @{acc['username']}", 
                    callback_data=f"sel_ig_{acc['id']}_{acc['username']}"
                )])
            
            keyboard.append([InlineKeyboardButton("🔙 Quay lại", callback_data='back')])
            reply_markup = InlineKeyboardMarkup(keyboard)
            await bot_msg.edit_text(
                msg + "\n📋 <b>Bước 3/5: Chọn tài khoản</b>",
                reply_markup=reply_markup,
                parse_mode='HTML'
            )
            return IG_SELECT_ACCOUNT
        else:
            keyboard = [[InlineKeyboardButton("🔙 Quay lại", callback_data='back')]]
            await bot_msg.edit_text(
                "😔 <b>Không tìm thấy tài khoản!</b>\n\n"
                "💡 <b>Kiểm tra lại:</b>\n"
                "  • Token có đúng không?\n"
                "  • T Header có hợp lệ không?\n"
                "  • Đã thêm tài khoản IG vào Golike chưa?",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='HTML'
            )
            return ConversationHandler.END
    except Exception as e:
        keyboard = [[InlineKeyboardButton("🔙 Quay lại", callback_data='back')]]
        await bot_msg.edit_text(
            f"❌ <b>Lỗi kết nối!</b>\n\n"
            f"⚠️ {str(e)}",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='HTML'
        )
        return ConversationHandler.END

async def instagram_account_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Xử lý chọn tài khoản Instagram"""
    query = update.callback_query
    await query.answer()
    
    data = query.data.split('_')
    acc_id = data[2]
    username = data[3]
    
    context.user_data['ig_acc_id'] = acc_id
    context.user_data['ig_username'] = username
    
    keyboard = [[InlineKeyboardButton("🔙 Quay lại", callback_data='back')]]
    await query.edit_message_text(
        f"✅ <b>Đã chọn: @{username}</b>\n\n"
        "📋 <b>Bước 4/5: Cookie</b>\n\n"
        "🍪 Vui lòng nhập <b>Cookie Instagram</b>:\n\n"
        "💡 <i>Lấy từ trình duyệt khi đăng nhập Instagram</i>",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )
    return IG_COOKIE

async def instagram_cookie_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Nhận cookie Instagram"""
    context.user_data['ig_cookie'] = update.message.text.strip()
    keyboard = [[InlineKeyboardButton("🔙 Quay lại", callback_data='back')]]
    await update.message.reply_text(
        "� <b>Bước 5/6: Cấu hình</b>\n\n"
        "�🔢 Nhập <b>số lượng Job</b> muốn chạy:\n\n"
        "💡 <i>Nên chạy 20-100 jobs mỗi lần</i>",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )
    return IG_JOBS

async def instagram_jobs_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Nhận số lượng jobs với validation"""
    try:
        limit = int(update.message.text.strip())
        
        # Validation: Jobs should be between 1 and 500
        if not 1 <= limit <= 500:
            keyboard = [[InlineKeyboardButton("🔙 Quay lại", callback_data='back')]]
            await update.message.reply_text(
                "⚠️ <b>Số lượng không hợp lệ!</b>\n\n"
                "Số jobs phải từ <code>1</code> đến <code>500</code>\n\n"
                "💡 <i>Ví dụ:  50</i>",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='HTML'
            )
            return IG_JOBS
        
        context.user_data['ig_limit'] = limit
        keyboard = [[InlineKeyboardButton("🔙 Quay lại", callback_data='back')]]
        await update.message.reply_text(
            "⏱️ Nhập <b>thời gian chờ</b> giữa các Job (giây):\n\n"
            "💡 <i>Nên ≥ 10s để tránh bị spam</i>",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='HTML'
        )
        return IG_DELAY
    except ValueError:
        keyboard = [[InlineKeyboardButton("🔙 Quay lại", callback_data='back')]]
        await update.message.reply_text(
            "❌ <b>Vui lòng nhập một con số!</b>\n\n"
            "💡 Ví dụ: <code>50</code>",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='HTML'
        )
        return IG_JOBS

async def instagram_delay_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Nhận delay với validation"""
    try:
        delay = int(update.message.text.strip())
        
        # Validation: Delay should be >= 5 seconds
        if delay < 5:
            keyboard = [[InlineKeyboardButton("🔙 Quay lại", callback_data='back')]]
            await update.message.reply_text(
                "⚠️ <b>Delay quá ngắn!</b>\n\n"
                "Delay phải ≥ <code>5 giây</code>\n\n"
                "💡 <i>Khuyến khích: 10-30 giây</i>",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='HTML'
            )
            return IG_DELAY
        
        context.user_data['ig_delay'] = delay
        
        # Show confirmation with all settings
        confirmation_text = (
            "🔍 <b>KIỂM TRA LẠI THÔNG TIN</b>\n"
            "──────────────\n\n"
            "📱 <b>Nền tảng:</b> Instagram\n"
            f"👤 <b>Tài khoản:</b> @{context.user_data['ig_username']}\n"
            f"🔢 <b>Số Jobs:</b> {context.user_data['ig_limit']}\n"
            f"⏱️ <b>Delay:</b> {delay}s\n\n"
            "──────────────\n"
            "✅ <b>Xác nhận để bắt đầu automation?</b>"
        )
        keyboard = [
            [InlineKeyboardButton("✅ Bắt đầu ngay!", callback_data='ig_confirm_yes')],
            [InlineKeyboardButton("🔙 Quay lại", callback_data='back')]
        ]
        await update.message.reply_text(
            confirmation_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='HTML'
        )
        return IG_CONFIRM
    except ValueError:
        keyboard = [[InlineKeyboardButton("🔙 Quay lại", callback_data='back')]]
        await update.message.reply_text(
            "❌ <b>Vui lòng nhập một con số!</b>\n\n"
            "💡 Ví dụ: <code>15</code>",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='HTML'
        )
        return IG_DELAY

async def instagram_confirm_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Xử lý xác nhận và bắt đầu automation"""
    query = update.callback_query
    await query.answer()
    
    if query.data != 'ig_confirm_yes':
        return IG_CONFIRM
    
    user_id = update.effective_user.id
    
    if user_id in instagram_automations:
        keyboard = [[InlineKeyboardButton("🔙 Menu chính", callback_data='back')]]
        await query.edit_message_text(
            "⚠️ <b>Bạn đã có automation đang chạy!</b>\n\n"
            "💡 Dùng /stop để dừng trước khi bắt đầu mới",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='HTML'
        )
        return ConversationHandler.END

    await query.edit_message_text("🚀 <b>Đang khởi tạo Instagram automation...</b>", parse_mode='HTML')
    
    try:
        api = InstagramAutomation()
        api.setup(
            context.user_data['ig_token'],
            context.user_data['ig_t'],
            context.user_data['ig_acc_id'],
            context.user_data['ig_cookie']
        )
        
        instagram_automations[user_id] = api
        
        # Initialize session tracking
        if user_id not in automation_sessions:
            automation_sessions[user_id] = {}
        
        automation_sessions[user_id]['ig'] = {
            'start_time': time.time(),
            'username': context.user_data['ig_username'],
            'target_jobs': context.user_data['ig_limit'],
            'completed_jobs': 0,
            'failed_jobs': 0,
            'total_earned': 0,
            'current_status': 'Đang khởi động...',
            'delay': context.user_data['ig_delay'],
            'last_job_time': time.time()
        }
        
        loop = asyncio.get_running_loop()
        
        # LUÔN GỬI MESSAGE MỚI - Không edit/xóa
        async def send_status_update(text):
            try:
                # Skip consecutive duplicates only
                last_text = context.user_data.get('ig_last_msg_text', '')
                if text == last_text:
                    return
                
                context.user_data['ig_last_msg_text'] = text
                
                # ALWAYS send NEW message - MỖI JOB MỘT MESSAGE RIÊNG
                await context.bot.send_message(
                    chat_id=update.effective_chat.id, 
                    text=text, 
                    parse_mode='HTML'
                )
            except Exception as e:
                logging.error(f"Error sending status: {e}")

        # Callback để gửi tin nhắn Telegram từ thread
        def sync_callback(msg, stats):
            stats['username'] = context.user_data['ig_username']
            
            # Update session stats
            if user_id in automation_sessions and 'ig' in automation_sessions[user_id]:
                automation_sessions[user_id]['ig']['completed_jobs'] = stats.get('completed_jobs', 0)
                automation_sessions[user_id]['ig']['failed_jobs'] = stats.get('failed_jobs', 0)
                automation_sessions[user_id]['ig']['total_earned'] = stats.get('total_earned', 0)
                automation_sessions[user_id]['ig']['current_status'] = msg[:50]  # First 50 chars of status
                automation_sessions[user_id]['ig']['last_job_time'] = time.time()  # Track last activity
            
            progress_text = format_progress_message("Instagram", msg, stats, context.user_data['ig_username'])
            asyncio.run_coroutine_threadsafe(
                send_status_update(progress_text),
                loop
            )

        # Chạy trong thread riêng
        thread = threading.Thread(
            target=api.run, 
            args=(context.user_data['ig_limit'], context.user_data['ig_delay'], sync_callback),
            daemon=True
        )
        thread.start()
        
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=(
                "✅ <b>Đã bắt đầu Instagram automation!</b>\n\n"
                f"👤 Account: @{context.user_data['ig_username']}\n"
                f"🔢 Jobs: {context.user_data['ig_limit']}\n"
                f"⏱️ Delay: {context.user_data['ig_delay']}s\n\n"
                "💡 Dùng /stop để dừng bất kỳ lúc nào\n"
                "📈 Dùng /thongke để xem thống kê chi tiết"
            ),
            parse_mode='HTML'
        )
        return ConversationHandler.END
    except Exception as e:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"❌ <b>Lỗi khởi tạo:</b> {str(e)}",
            parse_mode='HTML'
        )
        return ConversationHandler.END

async def instagram_delay(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        limit = int(update.message.text)
        context.user_data['ig_limit'] = limit
        await update.message.reply_text("⏱️ Nhập thời gian chờ giữa các Job (giây, ví dụ: 30):")
        return INSTAGRAM_LIMIT + 10 # temp state for starting
    except:
        await update.message.reply_text("❌ Vui lòng nhập một con số!")
        return INSTAGRAM_DELAY

async def start_instagram(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        delay = int(update.message.text)
        user_id = update.effective_user.id
        
        if user_id in instagram_automations:
            await update.message.reply_text("⚠️ Bạn đã có một automation đang chạy!")
            return ConversationHandler.END

        await update.message.reply_text("🚀 Đang khởi tạo Instagram automation...")
        
        api = InstagramAutomation()
        api.setup(
            context.user_data['ig_token'],
            context.user_data['ig_t'],
            context.user_data['ig_acc_id'],
            context.user_data['ig_cookie']
        )
        
        instagram_automations[user_id] = api
        
        # Capture the loop
        loop = asyncio.get_running_loop()
        
        # Helper để gửi/edit tin nhắn
        async def send_status_update(text):
            try:
                # Check if message is different from last one
                last_text = context.user_data.get('ig_last_msg_text', '')
                if text == last_text:
                    return  # Skip duplicate messages
                
                context.user_data['ig_last_msg_text'] = text
                msg_id = context.user_data.get('ig_status_msg_id')
                if msg_id:
                    try:
                        await context.bot.edit_message_text(
                            chat_id=update.effective_chat.id, 
                            message_id=msg_id, 
                            text=text, 
                            parse_mode='HTML'
                        )
                        return
                    except Exception: 
                        pass # Nếu edit lỗi, gửi mới
                
                msg = await context.bot.send_message(
                    chat_id=update.effective_chat.id, 
                    text=text, 
                    parse_mode='HTML'
                )
                context.user_data['ig_status_msg_id'] = msg.message_id
            except Exception as e:
                logging.error(f"Error sending status: {e}")

        # Callback để gửi tin nhắn Telegram từ thread
        def sync_callback(msg, stats):
            # Cập nhật context để UI đẹp hơn
            stats['username'] = context.user_data['ig_username']
            progress_text = format_progress_message("Instagram", msg, stats, context.user_data['ig_username'])
            
            # Gửi tin nhắn bất đồng bộ từ thread đồng bộ
            asyncio.run_coroutine_threadsafe(
                send_status_update(progress_text),
                loop
            )

        # Chạy trong thread riêng
        thread = threading.Thread(
            target=api.run, 
            args=(context.user_data['ig_limit'], delay, sync_callback),
            daemon=True
        )
        thread.start()
        
        return ConversationHandler.END
    except Exception as e:
        await update.message.reply_text(f"❌ Lỗi: {str(e)}")
        return ConversationHandler.END

# --- LinkedIn Flow ---

async def linkedin_auth(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    token = update.message.text
    context.user_data['li_token'] = token
    await update.message.reply_text("🔑 Vui lòng nhập *T Header* cho LinkedIn Golike:")
    return LI_T_HEADER

async def linkedin_cookie(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if 'li_t' not in context.user_data:
        context.user_data['li_t'] = update.message.text
        bot_msg = await update.message.reply_text("⏳ Đang kiểm tra tài khoản LinkedIn...")
        
        api = LinkedInAutomation()
        accounts = api.get_accounts(context.user_data['li_token'], context.user_data['li_t'])
        
        if accounts:
            context.user_data['li_accounts'] = accounts
            keyboard = []
            for acc in accounts:
                keyboard.append([InlineKeyboardButton(f"Chọn {acc['username']}", callback_data=f"sel_li_{acc['id']}_{acc['username']}")])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await bot_msg.edit_text("✅ Chọn tài khoản LinkedIn để chạy:", reply_markup=reply_markup)
            return LI_T_HEADER
        else:
            await bot_msg.edit_text("❌ Không thể lấy danh sách tài khoản LinkedIn!")
            return ConversationHandler.END
    return LI_T_HEADER

async def linkedin_account_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    
    data = query.data.split('_')
    acc_id = data[2]
    # Handle usernames with underscores by joining the rest of the parts
    username = "_".join(data[3:])
    
    context.user_data['li_acc_id'] = acc_id
    context.user_data['li_username'] = username
    
    await query.edit_message_text(
        f"🍪 Đã chọn account: @{data[3]}\n\n"
        "Vui lòng nhập *Cookie LinkedIn* cho tài khoản này:"
    )
    return LI_COOKIE

async def linkedin_get_cookie(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['li_cookie'] = update.message.text
    await update.message.reply_text("🔢 Nhập số lượng Job LinkedIn muốn chạy:")
    return LI_JOBS

async def linkedin_jobs(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        limit = int(update.message.text)
        context.user_data['li_limit'] = limit
        await update.message.reply_text("⏱️ Nhập thời gian chờ (giây):")
        return LI_DELAY
    except:
        await update.message.reply_text("❌ Nhập con số!")
        return LI_JOBS

async def start_linkedin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        delay = int(update.message.text)
        user_id = update.effective_user.id
        
        api = LinkedInAutomation()
        api.setup(
            context.user_data['li_token'],
            context.user_data['li_t'],
            context.user_data['li_acc_id'],
            context.user_data['li_cookie']
        )
        
        linkedin_automations[user_id] = api
        
        # Initialize session tracking
        if user_id not in automation_sessions:
            automation_sessions[user_id] = {}
        
        automation_sessions[user_id]['li'] = {
            'start_time': time.time(),
            'username': context.user_data['li_username'],
            'target_jobs': context.user_data['li_limit'],
            'completed_jobs': 0,
            'failed_jobs': 0,
            'total_earned': 0,
            'current_status': 'Đang khởi động...',
            'delay': delay,
            'last_job_time': time.time()
        }
        
        # Capture the loop
        loop = asyncio.get_running_loop()

        # LUÔN GỬI MESSAGE MỚI - Không edit/xóa
        async def send_status_update(text):
            try:
                # Skip consecutive duplicates only
                last_text = context.user_data.get('li_last_msg_text', '')
                if text == last_text:
                    return
                
                context.user_data['li_last_msg_text'] = text
                
                # ALWAYS send NEW message - MỖI JOB MỘT MESSAGE RIÊNG
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=text, 
                    parse_mode='HTML'
                )
            except Exception as e:
                logging.error(f"Error sending status: {e}")

        def sync_callback(msg, stats):
            # Update session stats
            if user_id in automation_sessions and 'li' in automation_sessions[user_id]:
                automation_sessions[user_id]['li']['completed_jobs'] = stats.get('completed_jobs', 0)
                automation_sessions[user_id]['li']['failed_jobs'] = stats.get('failed_jobs', 0)
                automation_sessions[user_id]['li']['total_earned'] = stats.get('total_earned', 0)
                automation_sessions[user_id]['li']['current_status'] = msg[:50]
                automation_sessions[user_id]['li']['last_job_time'] = time.time()  # Track last activity
            
            progress_text = format_progress_message("LinkedIn", msg, stats, context.user_data['li_username'])
            asyncio.run_coroutine_threadsafe(
                send_status_update(progress_text),
                loop
            )

        thread = threading.Thread(
            target=api.run, 
            args=(context.user_data['li_limit'], delay, sync_callback),
            daemon=True
        )
        thread.start()
        
        await update.message.reply_text(
            "🚀 <b>LinkedIn automation đã bắt đầu!</b>\n\n"
            f"👤 Account: @{context.user_data['li_username']}\n"
            f"🔢 Jobs: {context.user_data['li_limit']}\n"
            f"⏱️ Delay: {delay}s\n\n"
            "💡 Dùng /stop để dừng bất kỳ lúc nào\n"
            "📈 Dùng /thongke để xem thống kê chi tiết",
            parse_mode='HTML'
        )
        return ConversationHandler.END
    except Exception as e:
        await update.message.reply_text(f"❌ Lỗi: {str(e)}")
        return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("🛑 Đã hủy thao tác.")
    return ConversationHandler.END

async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Reset conversation state - giúp thoát khỏi conversation bị stuck"""
    user_id = update.effective_user.id
    
    # Clear user data
    context.user_data.clear()
    
    # Stop any running automation
    if user_id in instagram_automations:
        instagram_automations[user_id].stop()
        del instagram_automations[user_id]
        
    if user_id in linkedin_automations:
        linkedin_automations[user_id].stop()
        del linkedin_automations[user_id]
    
    # Clear session stats
    if user_id in automation_sessions:
        del automation_sessions[user_id]
    
    await update.message.reply_text(
        "🔄 Đã reset bot!\n\n"
        "Bạn có thể sử dụng /start để bắt đầu lại."
    )
    return ConversationHandler.END

async def stop_everything(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Dừng tất cả automation của người dùng"""
    user_id = update.effective_user.id
    stopped = False
    
    if user_id in instagram_automations:
        instagram_automations[user_id].stop()
        del instagram_automations[user_id]
        stopped = True
        
    if user_id in linkedin_automations:
        linkedin_automations[user_id].stop()
        del linkedin_automations[user_id]
        stopped = True
    
    # Clear session stats  
    if user_id in automation_sessions:
        del automation_sessions[user_id]
        
    if stopped:
        await update.message.reply_text("🛑 Đã gửi lệnh dừng tất cả automation!")
    else:
        await update.message.reply_text("⚠️ Bạn không có automation nào đang chạy!")



# --- Command Handlers ---

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    is_admin = (user_id == Config.ADMIN_USER_ID)
    
    help_text = (
        "⚡️━━━━━━━━━━━━━━━━━━━━━━⚡️\n"
        "           ⚽ <b>BÓNG X</b> ⚽\n"
        "⚡️━━━━━━━━━━━━━━━━━━━━━━⚡️\n\n"
        "┏━━━ <b>📋 LỆNH CƠ BẢN</b> ━━━┓\n"
        "┃  /start   → Khởi động bot         ┃\n"
        "┃  /help    → Xem hướng dẫn         ┃\n"
        "┃  /status  → Trạng thái hiện tại   ┃\n"
        "┃  /thongke → Xem thống kê chi tiết ┃\n"
        "┃  /stop    → Dừng automation       ┃\n"
        "┃  /reset   → Reset bot              ┃\n"
        "┗━━━━━━━━━━━━━━━━━━━━━━━┛\n\n"
        "┏━━ <b>📊 THỐNG KÊ</b> ━━┓\n"
        "┃  <b>/thongke</b> hoặc <b>/stats</b>     ┃\n"
        "┃                                   ┃\n"
        "┃  • Tốc độ chạy (jobs/phút)       ┃\n"
        "┃  • Tiến độ (%)                   ┃\n"
        "┃  • Thu nhập real-time            ┃\n"
        "┃  • Tỷ lệ thành công              ┃\n"
        "┗━━━━━━━━━━━━━━━━━━━━━━━┛\n\n"
    )
    
    if is_admin:
        help_text += (
            "┏━━ <b>👑 ADMIN PANEL</b> ━━┓\n"
            "┃  <b>/admin</b> - Quản lý hệ thống   ┃\n"
            "┃                                   ┃\n"
            "┃  • Tất cả users đang chạy        ┃\n"
            "┃  • Tốc độ & Hiệu suất            ┃\n"
            "┃  • Tổng thu nhập                 ┃\n"
            "┗━━━━━━━━━━━━━━━━━━━━━━━┛\n\n"
        )
    
    help_text += (
        "┏━━ <b>🔧 HƯỚNG DẪN</b> ━━┓\n"
        "┃                                   ┃\n"
        "┃  1️⃣ Chọn nền tảng (IG/LinkedIn)  ┃\n"
        "┃  2️⃣ Nhập Token + T Header        ┃\n"
        "┃  3️⃣ Chọn tài khoản               ┃\n"
        "┃  4️⃣ Nhập Cookie                  ┃\n"
        "┃  5️⃣ Cấu hình Jobs + Delay        ┃\n"
        "┃  6️⃣ Xác nhận và chạy!            ┃\n"
        "┃                                   ┃\n"
        "┗━━━━━━━━━━━━━━━━━━━━━━━┛\n\n"
        "💡 <b>GỢI Ý:</b>\n"
        "  • Delay ≥ 10s để tránh spam\n"
        "  • Dùng /thongke xem chi tiết\n"
        "  • Token lấy từ Golike\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━\n"
        "👨‍💻 <b>Trần Đức Doanh</b>\n"
        "👑 t.me/doanhvip1 • @doanhvip12\n"
        "━━━━━━━━━━━━━━━━━━━━━━━"
    )
    await update.message.reply_text(help_text, parse_mode='HTML')

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    msg = "📊 <b>TÌNH TRẠNG AUTOMATION</b>\n\n"
    
    ig_running = user_id in instagram_automations
    li_running = user_id in linkedin_automations
    
    if ig_running:
        msg += "✅ Instagram: <b>Đang chạy</b>\n"
    else:
        msg += "⭕ Instagram: Đang dừng\n"
        
    if li_running:
        msg += "✅ LinkedIn: <b>Đang chạy</b>\n"
    else:
        msg += "⭕ LinkedIn: Đang dừng\n"
    
    msg += "\n💡 Dùng /stop để dừng automation"
    msg += "\n📈 Dùng /thongke để xem chi tiết"
    await update.message.reply_text(msg, parse_mode='HTML')

async def thongke_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    # Check if user has any active sessions
    if user_id not in automation_sessions or not automation_sessions[user_id]:
        msg = (
            "📊 <b>THỐNG KÊ CHI TIẾT</b>\n"
            "═══════════════════\n\n"
            "⚠️ <i>Chưa có session nào đang chạy</i>\n\n"
            "💡 Sử dụng /start để bắt đầu automation"
        )
        await update.message.reply_text(msg, parse_mode='HTML')
        return
    
    msg = (
        "📊 <b>THỐNG KÊ CHI TIẾT</b>\n"
        "═══════════════════\n\n"
    )
    
    user_sessions = automation_sessions[user_id]
    total_earned = 0
    total_completed = 0
    total_failed = 0
    
    # Instagram stats
    if 'ig' in user_sessions and user_sessions['ig']:
        ig_stats = user_sessions['ig']
        start_time = ig_stats.get('start_time', time.time())
        running_time = int(time.time() - start_time)
        hours = running_time // 3600
        minutes = (running_time % 3600) // 60
        seconds = running_time % 60
        
        completed = ig_stats.get('completed_jobs', 0)
        failed = ig_stats.get('failed_jobs', 0)
        earned = ig_stats.get('total_earned', 0)
        username = ig_stats.get('username', 'N/A')
        target_jobs = ig_stats.get('target_jobs', 0)
        current_status = ig_stats.get('current_status', 'Đang chạy')
        
        total_earned += earned
        total_completed += completed
        total_failed += failed
        
        progress = (completed / target_jobs * 100) if target_jobs > 0 else 0
        
        msg += (
            "📸 <b>INSTAGRAM</b>\n"
            f"👤 Account: <code>@{username}</code>\n"
            f"⏱️ Thời gian chạy: <code>{hours:02d}:{minutes:02d}:{seconds:02d}</code>\n"
            f"📈 Tiến độ: <code>{completed}/{target_jobs}</code> ({progress:.1f}%)\n"
            f"✅ Hoàn thành: <code>{completed}</code> jobs\n"
            f"❌ Thất bại: <code>{failed}</code> jobs\n"
            f"💰 Tổng kiếm: <code>{earned:,}</code> VND\n"
            f"📊 Trạng thái: <i>{current_status}</i>\n"
            "───────────────────\n\n"
        )
    
    # LinkedIn stats
    if 'li' in user_sessions and user_sessions['li']:
        li_stats = user_sessions['li']
        start_time = li_stats.get('start_time', time.time())
        running_time = int(time.time() - start_time)
        hours = running_time // 3600
        minutes = (running_time % 3600) // 60
        seconds = running_time % 60
        
        completed = li_stats.get('completed_jobs', 0)
        failed = li_stats.get('failed_jobs', 0)
        earned = li_stats.get('total_earned', 0)
        username = li_stats.get('username', 'N/A')
        target_jobs = li_stats.get('target_jobs', 0)
        current_status = li_stats.get('current_status', 'Đang chạy')
        
        total_earned += earned
        total_completed += completed
        total_failed += failed
        
        progress = (completed / target_jobs * 100) if target_jobs > 0 else 0
        
        msg += (
            "💼 <b>LINKEDIN</b>\n"
            f"👤 Account: <code>@{username}</code>\n"
            f"⏱️ Thời gian chạy: <code>{hours:02d}:{minutes:02d}:{seconds:02d}</code>\n"
            f"📈 Tiến độ: <code>{completed}/{target_jobs}</code> ({progress:.1f}%)\n"
            f"✅ Hoàn thành: <code>{completed}</code> jobs\n"
            f"❌ Thất bại: <code>{failed}</code> jobs\n"
            f"💰 Tổng kiếm: <code>{earned:,}</code> VND\n"
            f"📊 Trạng thái: <i>{current_status}</i>\n"
            "───────────────────\n\n"
        )
    
    # Tổng kết
    if total_completed > 0 or total_failed > 0:
        success_rate = (total_completed / (total_completed + total_failed) * 100) if (total_completed + total_failed) > 0 else 0
        msg += (
            "📊 <b>TỔNG KẾT</b>\n"
            f"✅ Jobs hoàn thành: <code>{total_completed}</code>\n"
            f"❌ Jobs thất bại: <code>{total_failed}</code>\n"
            f"📈 Tỷ lệ thành công: <code>{success_rate:.1f}%</code>\n"
            f"💰 <b>Tổng thu nhập: <code>{total_earned:,} VND</code></b>\n"
            "═══════════════════\n\n"
            "💡 Sử dụng /stop để dừng automation"
        )
    
    await update.message.reply_text(msg, parse_mode='HTML')

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    # Check if user is admin
    if user_id != Config.ADMIN_USER_ID:
        await update.message.reply_text("⛔ Bạn không có quyền sử dụng lệnh này!")
        return
    
    msg = (
        "👑 <b>ADMIN PANEL</b>\n"
        "═══════════════════\n\n"
    )
    
    # Tổng số người đang dùng bot
    total_users = len(automation_sessions)
    
    if total_users == 0:
        msg += "⚠️ <i>Hiện không có user nào đang chạy automation</i>\n\n"
        msg += f"📊 Tổng user đã dùng bot: <code>{len(user_info)}</code>\n"
        await update.message.reply_text(msg, parse_mode='HTML')
        return
    
    msg += f"👥 <b>Số người đang online: {total_users}</b>\n"
    msg += "═══════════════════\n\n"
    
    total_all_earned = 0
    total_all_jobs = 0
    
    # Hiển thị từng user
    for uid, sessions in automation_sessions.items():
        user_data = user_info.get(uid, {'username': 'Unknown', 'first_name': 'Unknown'})
        username = user_data.get('username', 'N/A')
        first_name = user_data.get('first_name', 'Unknown')
        
        msg += f"👤 <b>{first_name}</b> (@{username})\n"
        msg += f"📱 ID: <code>{uid}</code>\n"
        
        user_total_earned = 0
        user_total_jobs = 0
        
        # Instagram
        if 'ig' in sessions and sessions['ig']:
            ig = sessions['ig']
            running_time = time.time() - ig['start_time']
            hours = int(running_time // 3600)
            minutes = int((running_time % 3600) // 60)
            
            completed = ig['completed_jobs']
            earned = ig['total_earned']
            delay = ig.get('delay', 0)
            
            # Tính tốc độ (jobs/phút)
            if running_time > 0:
                speed = (completed / running_time) * 60  # jobs per minute
            else:
                speed = 0
            
            # Tốc độ mong đợi (1 job mỗi delay seconds)
            if delay > 0:
                expected_speed = 60 / delay  # jobs per minute
                efficiency = (speed / expected_speed * 100) if expected_speed > 0 else 0
            else:
                expected_speed = 0
                efficiency = 0
            
            user_total_earned += earned
            user_total_jobs += completed
            
            msg += (
                f"  📸 <b>Instagram</b>: @{ig['username']}\n"
                f"    ✅ Jobs: <code>{completed}/{ig['target_jobs']}</code>\n"
                f"    ⚡ Tốc độ: <code>{speed:.2f}</code> jobs/phút\n"
                f"    📊 Hiệu suất: <code>{efficiency:.1f}%</code>\n"
                f"    ⏱️ Đã chạy: <code>{hours}h{minutes:02d}m</code>\n"
                f"    💰 Kiếm: <code>{earned:,}</code> VND\n"
            )
        
        # LinkedIn
        if 'li' in sessions and sessions['li']:
            li = sessions['li']
            running_time = time.time() - li['start_time']
            hours = int(running_time // 3600)
            minutes = int((running_time % 3600) // 60)
            
            completed = li['completed_jobs']
            earned = li['total_earned']
            delay = li.get('delay', 0)
            
            # Tính tốc độ
            if running_time > 0:
                speed = (completed / running_time) * 60
            else:
                speed = 0
            
            if delay > 0:
                expected_speed = 60 / delay
                efficiency = (speed / expected_speed * 100) if expected_speed > 0 else 0
            else:
                expected_speed = 0
                efficiency = 0
            
            user_total_earned += earned
            user_total_jobs += completed
            
            msg += (
                f"  💼 <b>LinkedIn</b>: @{li['username']}\n"
                f"    ✅ Jobs: <code>{completed}/{li['target_jobs']}</code>\n"
                f"    ⚡ Tốc độ: <code>{speed:.2f}</code> jobs/phút\n"
                f"    📊 Hiệu suất: <code>{efficiency:.1f}%</code>\n"
                f"    ⏱️ Đã chạy: <code>{hours}h{minutes:02d}m</code>\n"
                f"    💰 Kiếm: <code>{earned:,}</code> VND\n"
            )
        
        msg += f"  💵 Tổng: <b>{user_total_earned:,} VND</b> ({user_total_jobs} jobs)\n"
        msg += "───────────────────\n\n"
        
        total_all_earned += user_total_earned
        total_all_jobs += user_total_jobs
    
    # Tổng kết toàn bot
    msg += (
        "📊 <b>TỔNG KẾT HỆ THỐNG</b>\n"
        f"👥 Users đang chạy: <code>{total_users}</code>\n"
        f"✅ Tổng jobs: <code>{total_all_jobs}</code>\n"
        f"💰 Tổng thu nhập: <b><code>{total_all_earned:,} VND</code></b>\n"
        "═══════════════════"
    )
    
    await update.message.reply_text(msg, parse_mode='HTML')


def main():
    # Validate configuration
    print("=" * 50)
    print("🤖 TELEGRAM BOT AUTOMATION STARTING")
    print("=" * 50)
    
    # Handler xử lý command khi đang ở trong hội thoại
    
    # 1. Hàm wrapper cho Start để nó hoạt động như một lệnh Reset cứng trong mọi tình huống
    async def start_fallback(update: Update, context: ContextTypes.DEFAULT_TYPE):
        # Clear data cũ trước
        context.user_data.clear()
        # Gọi lại hàm start gốc
        return await start(update, context)

    # 2. Wrappers cho các lệnh thông tin (giữ nguyên state)
    async def thongke_fallback(update: Update, context: ContextTypes.DEFAULT_TYPE):
        await thongke_command(update, context)
        # return None để giữ nguyên state hiện tại (không bị out ra ngoài)
    
    async def status_fallback(update: Update, context: ContextTypes.DEFAULT_TYPE):
        await status_command(update, context)
    
    async def help_fallback(update: Update, context: ContextTypes.DEFAULT_TYPE):
        await help_command(update, context)

    async def admin_fallback(update: Update, context: ContextTypes.DEFAULT_TYPE):
        await admin_command(update, context)
    
    # Display config status
    if Config.ALLOWED_USER_IDS is not None and len(Config.ALLOWED_USER_IDS) > 0:
        print(f"🔒 Access Control: ENABLED ({len(Config.ALLOWED_USER_IDS)} user(s))")
        print(f"   Allowed IDs: {Config.ALLOWED_USER_IDS}")
    else:
        print("🌐 Access Control: DISABLED (All users allowed)")
    
    if Config.TELEGRAM_BOT_TOKEN:
        token_preview = Config.TELEGRAM_BOT_TOKEN[:20] + "..." + Config.TELEGRAM_BOT_TOKEN[-10:]
        print(f"🔑 Bot Token: {token_preview}")
    else:
        print("❌ ERROR: No bot token found!")
        return
    
    print("=" * 50)
    
    application = ApplicationBuilder().token(Config.TELEGRAM_BOT_TOKEN).build()
    
    # Conversation Handler tối ưu hóa
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler('start', start),
        ],
        states={
            MAIN_MENU: [
                CallbackQueryHandler(menu_callback, pattern='^(ig|li|status|help|back|stop_all)$'),
                CommandHandler('stop', stop_everything),
            ],
            # Instagram flow
            IG_AUTH: [MessageHandler(filters.TEXT & ~filters.COMMAND, instagram_auth)],
            IG_T_HEADER: [MessageHandler(filters.TEXT & ~filters.COMMAND, instagram_t_header)],
            IG_SELECT_ACCOUNT: [
                CallbackQueryHandler(instagram_account_callback, pattern='^sel_ig_'),
                CallbackQueryHandler(menu_callback, pattern='^back$'),
            ],
            IG_COOKIE: [MessageHandler(filters.TEXT & ~filters.COMMAND, instagram_cookie_input)],
            IG_JOBS: [MessageHandler(filters.TEXT & ~filters.COMMAND, instagram_jobs_input)],
            IG_DELAY: [MessageHandler(filters.TEXT & ~filters.COMMAND, instagram_delay_input)],
            IG_CONFIRM: [
                CallbackQueryHandler(instagram_confirm_callback, pattern='^ig_confirm_yes$'),
                CallbackQueryHandler(menu_callback, pattern='^back$'),
            ],
            
            # LinkedIn flow
            LI_AUTH: [MessageHandler(filters.TEXT & ~filters.COMMAND, linkedin_auth)],
            LI_T_HEADER: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, linkedin_cookie),
                CallbackQueryHandler(linkedin_account_callback, pattern='^sel_li_')
            ],
            LI_COOKIE: [MessageHandler(filters.TEXT & ~filters.COMMAND, linkedin_get_cookie)],
            LI_JOBS: [MessageHandler(filters.TEXT & ~filters.COMMAND, linkedin_jobs)],
            LI_DELAY: [MessageHandler(filters.TEXT & ~filters.COMMAND, start_linkedin)],
        },
        fallbacks=[
            # QUAN TRỌNG: /start ở đây giúp user thoát khỏi mọi thế kẹt
            CommandHandler('start', start_fallback),
            
            # Các lệnh thoát/reset khác
            CommandHandler('cancel', cancel),
            CommandHandler('reset', reset),
            CommandHandler('stop', stop_everything),
            CommandHandler('strop', stop_everything),
            
            # Các lệnh xem thông tin (Non-blocking)
            CommandHandler('thongke', thongke_fallback),
            CommandHandler('stats', thongke_fallback),
            CommandHandler('status', status_fallback),
            CommandHandler('help', help_fallback),
            CommandHandler('admin', admin_fallback),
            
            CallbackQueryHandler(menu_callback, pattern='^back$'),
        ],
        per_message=False,
    )
    
    # Add handler
    application.add_handler(conv_handler)
    
    # Add commands global
    application.add_handler(CommandHandler('start', start)) # Backup
    application.add_handler(CommandHandler('help', help_command))
    application.add_handler(CommandHandler('status', status_command))
    application.add_handler(CommandHandler('thongke', thongke_command))
    application.add_handler(CommandHandler('stats', thongke_command))
    application.add_handler(CommandHandler('admin', admin_command))
    application.add_handler(CommandHandler('reset', reset))
    application.add_handler(CommandHandler('stop', stop_everything))
    
    print("🚀 Bot is starting...")
    print("📡 Using polling mode (long-polling)")
    print("🌐 Waiting for incoming messages...")
    print("=" * 50)
    application.run_polling()

if __name__ == '__main__':
    keep_alive()
    main()
