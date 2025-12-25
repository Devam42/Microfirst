# 🤖 Microbot - AI Voice Assistant

A smart AI-powered voice assistant with natural language processing, reminders, and note-taking capabilities.

## ✨ Features

- 🧠 **AI Chat**: Natural conversations powered by Google Gemini
- 🎙️ **Voice Mode**: Continuous voice conversation with STT/TTS
- 📝 **Smart Reminders**: Natural language reminder creation
- 📓 **Notes**: Quick note-taking and organization
- 🌍 **Multilingual**: English and Hinglish support

## 🚀 Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Setup Credentials

Create a `.env` file from the example:

```bash
copy env.example .env
```

Edit `.env` and add your API keys:

```env
# Required for AI chat
GOOGLE_API_KEY=your_google_gemini_api_key

# Required for voice features
AWS_ACCESS_KEY_ID=your_aws_access_key
AWS_SECRET_ACCESS_KEY=your_aws_secret_key
AWS_DEFAULT_REGION=ap-south-1
```

**Get API Keys:**
- Google Gemini: https://makersuite.google.com/app/apikey
- AWS Console: https://console.aws.amazon.com/iam/

### 3. Run the Server

```bash
python api_server.py
```

Server will start on `http://localhost:5000`

## 📖 Usage

### Voice Conversation

1. Open the web UI: `test_ui.html` in your browser
2. Click "Start Continuous Voice"
3. Speak naturally to have a conversation

### Examples

```
You: "Remind me in 5 minutes to call mom"
Bot: ✅ Reminder set! I'll remind you to call mom in 5 minutes.

You: "How much time is remaining for the reminder?"
Bot: Next reminder: 'call mom' in 3m 45s

You: "Take a note: Buy groceries tomorrow"
Bot: ✅ Note saved!
```

## 🔌 API Endpoints

- `POST /api/talk/continuous/start` - Start voice mode
- `POST /api/talk/continuous/stop` - Stop voice mode
- `GET /api/talk/continuous/status` - Check status
- `GET /api/config` - Get configuration
- `GET /api/data/reminders` - Get all reminders
- `GET /api/data/notes` - Get all notes
- `GET /api/health` - Health check

Full API docs: `http://localhost:5000/docs`

## 📁 Project Structure

```
microbot/
├── api_server.py              # FastAPI REST server
├── requirements.txt           # Dependencies
├── .env                       # API credentials (create from env.example)
├── config.json                # Bot settings (auto-generated)
├── reminders.json             # Reminder storage
├── notes.json                 # Notes storage
├── test_ui.html              # Web interface
│
└── microbot/                  # Main package
    ├── core/                  # Chat management, conversation handling
    ├── features/              # Reminders, notes, voice, language
    └── utils/                 # Config, time parsing
```

## 🐛 Troubleshooting

### Error: "GEMINI_API_KEY missing"

1. Create `.env` file: `copy env.example .env`
2. Add your Google Gemini API key
3. Restart the server

### Error: "AWS credentials not provided"

- **For text-only**: Ignore this, chat will work fine
- **For voice mode**: Add AWS credentials to `.env`

### Voice not working

1. Check microphone permissions in browser
2. Verify AWS credentials are correct in `.env`
3. Check console for error messages

## 🔐 Security

- ✅ All credentials stored in `.env` (never committed to Git)
- ✅ Password protection with SHA-256 hashing
- ✅ No hardcoded API keys in codebase

## 📝 License

MIT

---

Built with ❤️ using Google Gemini AI, FastAPI, and AWS Polly
