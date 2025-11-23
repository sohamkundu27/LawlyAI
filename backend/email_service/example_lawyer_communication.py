"""
Example script demonstrating how to use the email agent for lawyer communications.

This script shows how to:
1. Initialize the email agent
2. Set a list of lawyer emails
3. Send initial messages to all lawyers
4. Monitor and maintain ongoing communication
"""

import os
from dotenv import load_dotenv
from email_agent import create_email_agent, initialize_lawyer_communications
from email_listener import listen_loop

load_dotenv()


def main():
    """Example: Initialize lawyer communications and start listening for responses."""
    
    # Check configuration
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        print("[ERROR] GEMINI_API_KEY not set in .env file")
        return
    
    sender_email = os.getenv("SENDER_EMAIL")
    sender_password = os.getenv("SENDER_PASSWORD")
    
    if sender_email == "your-email@gmail.com" or sender_password == "your-app-password":
        print("[ERROR] Please configure SENDER_EMAIL and SENDER_PASSWORD in your .env file")
        return
    
    # Create email agent
    print("🤖 Initializing Email Agent...")
    agent = create_email_agent(api_key=api_key)
    print("✅ Agent ready!\n")
    
    # Example: Set lawyer emails
    # Replace these with actual lawyer email addresses
    lawyer_emails = [
        "sohamkundu2704@gmail.com",
        "jaybalu06@gmail.com",
        "arnavmohanty123@gmail.com"
    ]
    
    # Optional: Customize initial message
    initial_subject = "Legal Consultation Inquiry"
    initial_message = """Hello,

I hope this email finds you well. I am reaching out to inquire about your legal services and would appreciate the opportunity to discuss my legal needs with you.

Could you please provide information about:
- Your areas of practice
- Your fee structure (hourly rate, flat fee, or contingency)
- Your availability for a consultation
- Any initial retainer requirements

Thank you for your time and consideration. I look forward to hearing from you.

Best regards"""
    
    # Initialize communications with lawyers
    print("=" * 60)
    print("STEP 1: Sending Initial Messages to Lawyers")
    print("=" * 60)
    results = initialize_lawyer_communications(
        agent=agent,
        lawyer_emails=lawyer_emails,
        initial_subject=initial_subject,
        initial_message=initial_message
    )
    
    # Show results
    print("\n📊 Results:")
    for email, result in results.items():
        status = "✅" if "successfully" in result.lower() else "❌"
        print(f"  {status} {email}: {result[:80]}...")
    
    # Check lawyer statuses
    print("\n" + "=" * 60)
    print("STEP 2: Lawyer Conversation Status")
    print("=" * 60)
    statuses = agent.get_all_lawyer_statuses()
    if statuses:
        for email, status in statuses.items():
            print(f"\n{email}:")
            print(f"  Status: {status.get('status', 'unknown')}")
            print(f"  Messages sent: {status.get('message_count', 0)}")
            print(f"  Initial contact: {status.get('initial_contact', 'N/A')}")
    else:
        print("No lawyer conversations tracked yet.")
    
    # Start listening for responses
    print("\n" + "=" * 60)
    print("STEP 3: Starting Email Listener")
    print("=" * 60)
    print("The agent will now monitor for incoming emails from lawyers")
    print("and automatically maintain the conversation.\n")
    print("Press Ctrl+C to stop.\n")
    
    # Start the listener loop (checks every 60 seconds)
    # Set auto_reply=True to automatically send replies
    # Set auto_reply=False to just generate replies without sending
    listen_loop(agent, check_interval=60, auto_reply=True)


if __name__ == "__main__":
    main()

