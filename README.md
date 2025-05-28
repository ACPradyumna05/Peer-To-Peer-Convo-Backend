# 💬 Peer-to-Peer Conversation Management System

A robust and scalable backend system for real-time one-on-one and group messaging, built with **Python (Flask)** and **MySQL**. This project demonstrates practical application of **DBMS concepts** in a modern web-based communication platform.

---

# Preview
> https://github.com/user-attachments/assets/7efadb8e-c8db-475b-920a-f0a4342ff815


## 🚀 Features

### 🔐 Authentication & User Management
- Secure user registration
- Unique usernames enforced

### 📬 Direct Messaging
- One-on-one message exchange
- Automatic chat session creation
- Read receipts with timestamps
- Message deletion with ownership checks

### 👥 Group Chat
- Group creation with admin roles
- Add/remove/list group members
- Group messaging with read tracking
- Permission-controlled message deletion

### 📊 Message Tracking
- Real-time read receipt generation
- Read status views (direct + group messages)

### 🧠 Intelligent Backend
- Action-based routing for clean API design
- Robust JSON parsing with error handling
- Secure connection lifecycle management

---

## 🧱 Database Design

All database tables are **normalized up to 3NF**, ensuring:
- ✅ Atomic, consistent data
- ✅ No redundancy or transitive dependencies
- ✅ Clean relational structure with foreign keys

> The schema supports core entities: `users`, `userChats`, `messages`, `read_receipts`, `groups`, `group_members`, `group_messages`, and `group_read_receipts`.

---

## 🛠️ Tech Stack

| Layer       | Technology          |
|-------------|---------------------|
| Backend     | Python (Flask)      |
| Database    | MySQL               |
| API Format  | JSON over WebSocket |
| Interface   | Terminal/WebSocket clients |

---

## ⚙️ Project Workflow

### 1. **User Registration**
- Endpoint: `register`
- Stores new users in the DB with unique usernames

### 2. **Direct Messaging**
- Send/receive messages
- Mark messages as read
- View message history
- Delete messages securely

### 3. **Group Messaging**
- Create and manage groups
- Send/receive group messages
- View who read each group message
- Group-based message deletion by sender/admin

---

## 🧪 Testing & Results

- All routes tested with valid and invalid inputs
- Real-time read receipts and message tracking work as expected
- Group permissions (admin, member) correctly enforced
- Secure error handling with clear, consistent responses
