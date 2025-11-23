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
from typing import Optional

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
    print("You can now ask the agent to send emails in natural language.")
    print("Example: 'Send an email to test@example.com with subject 'Hello' and body 'This is a test'")
    print("Type 'quit' to exit.\n")
    
    # Interactive loop
    while True:
        user_input = input("You: ").strip()
        
        if user_input.lower() in ['quit', 'exit', 'q']:
            print("👋 Goodbye!")
            break
        
        if not user_input:
            continue
        
        try:
            result = agent.invoke(user_input)
            print(f"\nAgent: {result['output']}\n")
        except Exception as e:
            print(f"❌ Error: {str(e)}\n")


if __name__ == "__main__":
    main()
