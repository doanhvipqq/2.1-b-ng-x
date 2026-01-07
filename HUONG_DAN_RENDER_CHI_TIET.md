# 🚀 HƯỚNG DẪN CÀI ĐẶT BOT LÊN RENDER (CHI TIẾT)

Bạn hãy làm theo đúng từng bước dưới đây. Đừng bỏ qua bước nào nhé!

## PHẦN 1: CHUẨN BỊ TRÊN RENDER

1.  Truy cập trang web: [https://dashboard.render.com/](https://dashboard.render.com/)
2.  Đăng nhập bằng tài khoản **GitHub** của bạn (User `doanhvipqq` mà bạn vừa push code lên).

---

## PHẦN 2: TẠO WEB SERVICE MỚI

Cách dễ nhất (Tự động):

1.  Trên Render Dashboard, bấm nút **"Blueprints"** (ở thanh menu trên cùng hoặc bên trái).
2.  Bấm nút **"New Blueprint Instance"**.
3.  Kết nối với GitHub Repository của bạn: `bong-x-bot` (hoặc `2.1-b-ng-x` mà bạn vừa tạo).
4.  Bấm **"Connect"**.
5.  Render sẽ tự động đọc file `render.yaml` trong code của bạn.

---

## PHẦN 3: CẤU HÌNH QUAN TRỌNG (BẮT BUỘC)

Sau khi bấm Connect, Render sẽ hiện ra một bảng yêu cầu nhập thông tin. Bạn sẽ thấy mục **Environment Variables** (Biến môi trường) hoặc **Env Vars**.

Bạn **PHẢI** điền thông tin sau:

| Key (Tên biến) | Value (Giá trị) |
| :--- | :--- |
| **TELEGRAM_BOT_TOKEN** | Dán token bot của bạn vào đây (Ví dụ: `8498886260:AAHf...`) |

⚠️ **Lưu ý:** Nếu bạn không điền dòng này, bot sẽ KHÔNG BAO GIỜ CHẠY được.

Sau đó bấm nút **"Apply"** hoặc **"Create Web Service"**.

---

## PHẦN 4: KIỂM TRA BOT (DEBUG)

Sau khi tạo xong, Render sẽ bắt đầu **Build** và **Deploy**. Quá trình này mất khoảng 2-3 phút.

1.  Bấm vào tên service vừa tạo (ví dụ `telegram-automation-bot`).
2.  Bấm vào tab **"Logs"** (Nhật ký) ở bên trái.
3.  Quan sát dòng chữ chạy lên màn hình.

**Dấu hiệu thành công:**
```
✅ Telegram bot connected
✅ Application started
🎬 STARTING BOT initialization...
📡 Using polling mode (long-polling)
🌐 Waiting for incoming messages...
```

**Dấu hiệu lỗi:**
- Nếu thấy: `Unauthorized` hoặc `Token Invalid` -> Bạn nhập sai Token.
- Nếu thấy: `Conflict: terminated by other getUpdates` -> Có một bot khác đang chạy Token này (có thể là máy tính của bạn chưa tắt hẳn).

---

## PHẦN 5: KHẮC PHỤC LỖI "BOT KHÔNG TRẢ LỜI"

Nếu Logs bảo chạy ngon lành mà Bot trên Telegram vẫn im lìm:

1.  Mở trình duyệt web tab mới.
2.  Chạy link sau để "thông nòng" cho bot (Thay `TOKEN_CUA_BAN` bằng token thật):
    `https://api.telegram.org/botTOKEN_CUA_BAN/deleteWebhook?drop_pending_updates=True`
3.  Nếu nó báo `{"ok":true...}` là xong.
4.  Quay lại Render, bấm **"Manual Deploy"** -> **"Restart Service"**.

---

## TÓM TẮT LẠI

1.  Lên Render -> New Blueprint -> Chọn Repo.
2.  Điền `TELEGRAM_BOT_TOKEN`.
3.  Đợi nó báo "Live" màu xanh lá cây.
4.  Vào Logs xem có lỗi đỏ không.
5.  Chat `/start` với bot.

Chúc bạn thành công! Nếu lỗi ở bước nào, hãy chụp ảnh màn hình cái Logs gửi mình nhé!
