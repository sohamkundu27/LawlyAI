"""
AI Agent for sending emails.
Uses LangChain with Google Gemini to create an agentic email sender that can reason about
when and how to send emails based on natural language instructions.
"""

import os
import smtplib
import json
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from typing import Optional, List, Set, Dict

from dotenv import load_dotenv
from langchain_core.tools import tool
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage

# Load environment variables from .env file
load_dotenv()


# Email configuration - set these as environment variables or modify here
SENDER_EMAIL = os.getenv("SENDER_EMAIL", "your-email@gmail.com")
SENDER_PASSWORD = os.getenv("SENDER_PASSWORD", "your-app-password")
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))


@tool
def send_email_tool(
    recipient_email: str,
    subject: str,
    body: str,
    sender_email: Optional[str] = None
) -> str:
    """
    Send an email to a recipient.
    
    Args:
        recipient_email: The email address to send to (required)
        subject: The subject line of the email (required)
        body: The body/content of the email (required)
        sender_email: Optional sender email (uses default if not provided)
    
    Returns:
        A string indicating success or failure
    """
    try:
        sender = sender_email or SENDER_EMAIL
        password = SENDER_PASSWORD
        
        if sender == "your-email@gmail.com" or password == "your-app-password":
            return "❌ Error: Please configure SENDER_EMAIL and SENDER_PASSWORD environment variables"
        
        # Create message
        message = MIMEMultipart()
        message["From"] = sender
        message["To"] = recipient_email
        message["Subject"] = subject
        
        # Add body to email
        message.attach(MIMEText(body, "plain"))
        
        # Create SMTP session
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()  # Enable encryption
        server.login(sender, password)
        
        # Send email
        text = message.as_string()
        server.sendmail(sender, recipient_email, text)
        server.quit()
        
        return f"✅ Email sent successfully to {recipient_email} with subject: '{subject}'"
        
    except smtplib.SMTPAuthenticationError as e:
        error_msg = str(e)
        if "Application-specific password" in error_msg or "534" in error_msg:
            return """❌ Gmail requires an App-Specific Password!
            
To fix this:
1. Go to https://myaccount.google.com/apppasswords
2. Sign in to your Google account
3. Select "Mail" and "Other (Custom name)"
4. Enter "Email Agent" as the name
5. Click "Generate"
6. Copy the 16-character password (no spaces)
7. Update your .env file: SENDER_PASSWORD=the-16-char-password

Note: You need 2-Step Verification enabled first.
If you don't have it, enable it at: https://myaccount.google.com/security"""
        return f"❌ Authentication error: {str(e)}"
    except Exception as e:
        return f"❌ Error sending email: {str(e)}"


class EmailAgent:
    """Simple agent that uses Google Gemini with tool calling to send emails."""
    
    def __init__(self, api_key: Optional[str] = None, model: str = "gemini-2.5-flash"):
        """
        Initialize the email agent.
        
        Args:
            api_key: Google Gemini API key (or set GEMINI_API_KEY env var)
            model: Model to use (default: gemini-2.5-flash for speed, or gemini-2.5-pro for better quality)
        """
        # Gemini API key can be set via GEMINI_API_KEY or GOOGLE_API_KEY env var
        api_key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY or GOOGLE_API_KEY must be set")
        
        self.llm = ChatGoogleGenerativeAI(
            model=model,
            temperature=0,
            google_api_key=api_key
        )
        
        # Bind tools to the LLM
        self.llm_with_tools = self.llm.bind_tools([send_email_tool])
        
        # Create prompt template
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a helpful AI assistant that can send emails on behalf of users.
            
You have access to a tool that can send emails. When a user asks you to send an email:
1. Extract the recipient email address, subject, and body content
2. Use the send_email_tool to send the email
3. Confirm the email was sent successfully

When generating email replies:
- Be professional, friendly, and helpful
- Match the tone of the original email
- Answer questions directly and clearly
- If you don't know something, say so politely
- Keep responses concise but complete

Be helpful and confirm what you're doing. If information is missing, ask the user for clarification."""),
            ("human", "{input}"),
        ])
        
        self.messages = []
        
        # Lawyer communication tracking
        self.lawyer_emails: Set[str] = set()
        self.lawyer_conversations: Dict[str, Dict] = {}  # email -> conversation metadata
        self.lawyer_initial_messages: Dict[str, Dict] = {}  # email -> initial message sent
    
    def invoke(self, input_text: str):
        """
        Process a user input and return the agent's response.
        
        Args:
            input_text: User's message
            
        Returns:
            Dictionary with 'output' key containing the agent's response
        """
        # Add user message
        self.messages.append(HumanMessage(content=input_text))
        
        # Get AI response with potential tool calls
        response = self.llm_with_tools.invoke(self.messages)
        self.messages.append(response)
        
        # Check if the model wants to call a tool
        while response.tool_calls:
            # Execute tool calls
            for tool_call in response.tool_calls:
                tool_name = tool_call["name"]
                tool_args = tool_call["args"]
                
                if tool_name == "send_email_tool":
                    result = send_email_tool.invoke(tool_args)
                    # Add tool result as a message
                    self.messages.append(
                        ToolMessage(
                            content=result,
                            tool_call_id=tool_call["id"]
                        )
                    )
            
            # Get the next response from the model
            response = self.llm_with_tools.invoke(self.messages)
            self.messages.append(response)
        
        return {"output": response.content}
    
    def set_lawyer_emails(self, lawyer_emails: List[str]):
        """
        Set the list of lawyer emails to communicate with.
        
        Args:
            lawyer_emails: List of lawyer email addresses
        """
        self.lawyer_emails = set(email.lower().strip() for email in lawyer_emails)
        print(f"✅ Set {len(self.lawyer_emails)} lawyer email(s) for communication")
    
    def add_lawyer_email(self, lawyer_email: str):
        """
        Add a single lawyer email to the communication list.
        
        Args:
            lawyer_email: Lawyer email address to add
        """
        self.lawyer_emails.add(lawyer_email.lower().strip())
        print(f"✅ Added lawyer email: {lawyer_email}")
    
    def get_lawyer_emails(self) -> List[str]:
        """Get the list of lawyer emails."""
        return list(self.lawyer_emails)
    
    def is_lawyer_email(self, email: str) -> bool:
        """Check if an email belongs to a tracked lawyer."""
        return email.lower().strip() in self.lawyer_emails
    
    def send_initial_message_to_lawyers(
        self, 
        subject: Optional[str] = None,
        message_template: Optional[str] = None,
        custom_messages: Optional[Dict[str, Dict[str, str]]] = None
    ) -> Dict[str, str]:
        """
        Send initial messages to all lawyer emails.
        
        Args:
            subject: Subject line for all emails (or auto-generated if None)
            message_template: Template message body (or auto-generated if None)
            custom_messages: Dict mapping email -> {subject: str, body: str} for custom messages per lawyer
        
        Returns:
            Dict mapping email -> result message
        """
        if not self.lawyer_emails:
            return {"error": "No lawyer emails set. Use set_lawyer_emails() first."}
        
        results = {}
        default_subject = subject or "Legal Consultation Inquiry"
        default_template = message_template or """Hello,

I hope this email finds you well. I am reaching out to inquire about your legal services and would appreciate the opportunity to discuss my legal needs with you.

Could you please provide information about:
- Your areas of practice
- Your fee structure (hourly rate, flat fee, or contingency)
- Your availability for a consultation
- Any initial retainer requirements

Thank you for your time and consideration. I look forward to hearing from you.

Best regards"""
        
        for lawyer_email in self.lawyer_emails:
            try:
                # Check for custom message
                if custom_messages and lawyer_email in custom_messages:
                    email_subject = custom_messages[lawyer_email].get('subject', default_subject)
                    email_body = custom_messages[lawyer_email].get('body', default_template)
                else:
                    email_subject = default_subject
                    email_body = default_template
                
                # Send email
                result = send_email_tool.invoke({
                    'recipient_email': lawyer_email,
                    'subject': email_subject,
                    'body': email_body
                })
                
                results[lawyer_email] = result
                
                # Track the initial message
                if "successfully" in result.lower():
                    self.lawyer_initial_messages[lawyer_email] = {
                        'subject': email_subject,
                        'body': email_body,
                        'sent_at': datetime.now().isoformat()
                    }
                    self.lawyer_conversations[lawyer_email] = {
                        'initial_contact': datetime.now().isoformat(),
                        'last_contact': datetime.now().isoformat(),
                        'message_count': 1,
                        'status': 'initial_sent'
                    }
                    print(f"✅ Initial message sent to {lawyer_email}")
                else:
                    print(f"❌ Failed to send initial message to {lawyer_email}: {result}")
                    
            except Exception as e:
                error_msg = f"Error sending to {lawyer_email}: {str(e)}"
                results[lawyer_email] = error_msg
                print(f"❌ {error_msg}")
        
        return results
    
    def update_lawyer_conversation(self, lawyer_email: str, email_data: Dict):
        """
        Update conversation tracking for a lawyer when they respond.
        
        Args:
            lawyer_email: The lawyer's email address
            email_data: Dictionary with email details (from, subject, body, etc.)
        """
        lawyer_email = lawyer_email.lower().strip()
        
        if lawyer_email not in self.lawyer_conversations:
            # First response from this lawyer
            self.lawyer_conversations[lawyer_email] = {
                'initial_contact': datetime.now().isoformat(),
                'last_contact': datetime.now().isoformat(),
                'message_count': 1,
                'status': 'responded'
            }
        else:
            # Update existing conversation
            self.lawyer_conversations[lawyer_email]['last_contact'] = datetime.now().isoformat()
            self.lawyer_conversations[lawyer_email]['message_count'] += 1
            self.lawyer_conversations[lawyer_email]['status'] = 'active'
    
    def get_lawyer_conversation_status(self, lawyer_email: str) -> Optional[Dict]:
        """Get conversation status for a lawyer."""
        return self.lawyer_conversations.get(lawyer_email.lower().strip())
    
    def get_all_lawyer_statuses(self) -> Dict[str, Dict]:
        """Get status of all lawyer conversations."""
        return self.lawyer_conversations.copy()
    
    def generate_lawyer_reply(
        self, 
        lawyer_email: str, 
        incoming_email: Dict,
        conversation_context: Optional[str] = None
    ) -> str:
        """
        Generate a reply to a lawyer's email, maintaining conversation context.
        
        Args:
            lawyer_email: The lawyer's email address
            incoming_email: Dictionary with incoming email details
            conversation_context: Optional conversation history context
            
        Returns:
            Generated reply text
        """
        # Update conversation tracking
        self.update_lawyer_conversation(lawyer_email, incoming_email)
        
        # Build context for reply generation
        context_parts = []
        
        if conversation_context:
            context_parts.append(f"Conversation history:\n{conversation_context}\n")
        
        # Check if this is a first response
        conv_status = self.get_lawyer_conversation_status(lawyer_email)
        if conv_status and conv_status.get('message_count', 0) == 1:
            context_parts.append("This is the lawyer's first response to your initial inquiry.")
        
        context_parts.append(f"\nIncoming email from {lawyer_email}:")
        context_parts.append(f"Subject: {incoming_email.get('subject', 'No subject')}")
        context_parts.append(f"Body:\n{incoming_email.get('body', '')}")
        
        context_parts.append("\n\nGenerate a professional, helpful reply that:")
        context_parts.append("- Acknowledges their response")
        context_parts.append("- Answers any questions they asked")
        context_parts.append("- Asks follow-up questions if appropriate")
        context_parts.append("- Maintains a professional but friendly tone")
        context_parts.append("- Keeps the conversation moving forward")
        
        prompt = "\n".join(context_parts)
        
        try:
            result = self.invoke(prompt)
            return result.get('output', '').strip()
        except Exception as e:
            print(f"Error generating reply: {str(e)}")
            return ""


def create_email_agent(api_key: Optional[str] = None, model: str = "gemini-2.5-flash"):
    """
    Create an AI agent that can send emails.
    
    Args:
        api_key: Google Gemini API key (or set GEMINI_API_KEY env var)
        model: Model to use (default: gemini-2.5-flash for speed, or gemini-2.5-pro for better quality)
    
    Returns:
        EmailAgent instance
    """
    return EmailAgent(api_key=api_key, model=model)


def initialize_lawyer_communications(
    agent: EmailAgent,
    lawyer_emails: List[str],
    initial_subject: Optional[str] = None,
    initial_message: Optional[str] = None
) -> Dict[str, str]:
    """
    Helper function to initialize communications with a set of lawyers.
    
    Args:
        agent: EmailAgent instance
        lawyer_emails: List of lawyer email addresses
        initial_subject: Optional custom subject for initial messages
        initial_message: Optional custom message body
    
    Returns:
        Dictionary mapping email -> result message
    """
    print(f"\n📧 Initializing communications with {len(lawyer_emails)} lawyer(s)...")
    
    # Set lawyer emails
    agent.set_lawyer_emails(lawyer_emails)
    
    # Send initial messages
    results = agent.send_initial_message_to_lawyers(
        subject=initial_subject,
        message_template=initial_message
    )
    
    print(f"\n✅ Initialization complete!")
    print(f"   Sent to: {sum(1 for r in results.values() if 'successfully' in r.lower())} lawyer(s)")
    print(f"   Failed: {sum(1 for r in results.values() if 'successfully' not in r.lower())} lawyer(s)")
    
    return results


def main():
    """Example usage of the email agent."""
    print("🤖 Initializing Email Agent (Google Gemini)...")
    
    # Check for API key
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        print("⚠️  Warning: GEMINI_API_KEY not set. Please set it in your .env file.")
        print("Get your API key from: https://makersuite.google.com/app/apikey")
        api_key = input("Enter your Google Gemini API key (or press Enter to skip): ").strip()
        if not api_key:
            print("❌ Cannot proceed without API key")
            return
    
    # Create agent
    agent = create_email_agent(api_key=api_key if api_key else None)
    
    print("\n✅ Email Agent ready!")
    print("\nAvailable commands:")
    print("  - 'lawyers <email1> <email2> ...' - Set lawyer emails and send initial messages")
    print("  - 'status' - Show status of all lawyer conversations")
    print("  - 'send <email> <subject> <body>' - Send a custom email")
    print("  - Or ask naturally: 'Send an email to test@example.com with subject 'Hello'")
    print("  - 'quit' to exit.\n")
    
    # Interactive loop
    while True:
        user_input = input("You: ").strip()
        
        if user_input.lower() in ['quit', 'exit', 'q']:
            print("👋 Goodbye!")
            break
        
        if not user_input:
            continue
        
        # Handle lawyer initialization command
        if user_input.lower().startswith('lawyers '):
            emails = user_input[8:].strip().split()
            if emails:
                results = initialize_lawyer_communications(agent, emails)
                for email, result in results.items():
                    print(f"  {email}: {result}")
            else:
                print("❌ Please provide at least one lawyer email address")
            continue
        
        # Handle status command
        if user_input.lower() == 'status':
            if hasattr(agent, 'get_all_lawyer_statuses'):
                statuses = agent.get_all_lawyer_statuses()
                if statuses:
                    print("\n📊 Lawyer Conversation Status:")
                    for email, status in statuses.items():
                        print(f"  {email}:")
                        print(f"    Status: {status.get('status', 'unknown')}")
                        print(f"    Messages: {status.get('message_count', 0)}")
                        print(f"    Last contact: {status.get('last_contact', 'N/A')}")
                else:
                    print("No lawyer conversations tracked yet.")
            else:
                print("Lawyer tracking not available.")
            continue
        
        # Handle custom send command
        if user_input.lower().startswith('send '):
            parts = user_input[5:].strip().split(' ', 2)
            if len(parts) >= 3:
                recipient, subject, body = parts
                result = send_email_tool.invoke({
                    'recipient_email': recipient,
                    'subject': subject,
                    'body': body
                })
                print(f"\n{result}\n")
            else:
                print("❌ Usage: send <email> <subject> <body>")
            continue
        
        # Regular natural language processing
        try:
            result = agent.invoke(user_input)
            print(f"\nAgent: {result['output']}\n")
        except Exception as e:
            print(f"❌ Error: {str(e)}\n")


if __name__ == "__main__":
    main()
