"""
Company Configuration for PDF Reports
Update these values with your actual company information
"""

# Company Information
COMPANY_NAME = "Shekru Labs India Pvt Ltd"
COMPANY_ADDRESS = "Office 2nd Floor, Manogat Appt., Treasure Park Road, Sahakar Nagar, Pune, Maharashtra 411009"
COMPANY_PHONE = "+91 7776827177"
COMPANY_EMAIL = "hr@shekruweb.com"
COMPANY_WEBSITE = "www.shekruweb.com"

# Watermark Configuration
WATERMARK_TEXT = "SHEKRU LABS"  # Text to show as watermark
WATERMARK_OPACITY = 0.1  # 0.0 (invisible) to 1.0 (fully visible)

# Color Scheme (Modern Blue Theme)
PRIMARY_COLOR = "#1e40af"  # Main brand color (blue)
SECONDARY_COLOR = "#3b82f6"  # Accent color (lighter blue)
TEXT_COLOR = "#0f172a"  # Dark text
LIGHT_BG_COLOR = "#eff6ff"  # Light background
GRAY_COLOR = "#64748b"  # Gray text

# Salary Slip Colors (matching sample)
HEADER_GREEN = "#4CAF50"  # Green header bar
HEADER_ORANGE = "#FF9800"  # Orange accent for logo

# Logo Configuration (Optional)
# Path to company logo used in PDFs (tracked in git)
LOGO_PATH = "assets/logo.png"  # Path to company logo
USE_LOGO = True  # Enable logo rendering in PDFs
LOGO_WIDTH = 2.5  # Logo width in inches
LOGO_HEIGHT = 2.0  # Logo height in inches (taller for clarity)

# Report Configuration
REPORT_TITLE = "EMPLOYEE DIRECTORY REPORT"
SHOW_EMOJIS = True  # Show role emojis (👑, 👥, 📊, etc.)
ALTERNATING_ROWS = True  # Alternate row colors for better readability
