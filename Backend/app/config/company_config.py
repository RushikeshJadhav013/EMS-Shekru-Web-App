"""
Company Configuration for PDF Reports
Update these values with your actual company information
"""

# Company Information
COMPANY_NAME = "YOUR COMPANY NAME"
COMPANY_ADDRESS = "Address Line 1, City, State - PIN Code"
COMPANY_PHONE = "+91-XXXXXXXXXX"
COMPANY_EMAIL = "info@company.com"
COMPANY_WEBSITE = "www.yourcompany.com"

# Watermark Configuration
WATERMARK_TEXT = "YOUR COMPANY"  # Text to show as watermark
WATERMARK_OPACITY = 0.1  # 0.0 (invisible) to 1.0 (fully visible)

# Color Scheme (Modern Blue Theme)
PRIMARY_COLOR = "#1e40af"  # Main brand color (blue)
SECONDARY_COLOR = "#3b82f6"  # Accent color (lighter blue)
TEXT_COLOR = "#0f172a"  # Dark text
LIGHT_BG_COLOR = "#eff6ff"  # Light background
GRAY_COLOR = "#64748b"  # Gray text

# Logo Configuration (Optional)
# Place your logo file in Backend/static/company_logo.png
LOGO_PATH = "static/company_logo.png"  # Path to company logo
USE_LOGO = False  # Set to True if you have a logo file
LOGO_WIDTH = 1.5  # Logo width in inches
LOGO_HEIGHT = 0.75  # Logo height in inches

# Report Configuration
REPORT_TITLE = "EMPLOYEE DIRECTORY REPORT"
SHOW_EMOJIS = True  # Show role emojis (👑, 👥, 📊, etc.)
ALTERNATING_ROWS = True  # Alternate row colors for better readability
