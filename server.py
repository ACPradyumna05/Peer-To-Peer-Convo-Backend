import asyncio
import websockets
import json
import mysql.connector
from datetime import datetime

db_config = {
    'user': 'root',
    'password': '', 
    'host': 'localhost',
    'database': 'chatdb'
}

conn = mysql.connector.connect(**db_config)
cursor = conn.cursor()

def setup_database():
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS groups (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(100) NOT NULL UNIQUE,
            created_by INT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (created_by) REFERENCES users(id)
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS group_members (
            id INT AUTO_INCREMENT PRIMARY KEY,
            group_id INT NOT NULL,
            user_id INT NOT NULL,
            joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (group_id) REFERENCES groups(id),
            FOREIGN KEY (user_id) REFERENCES users(id),
            UNIQUE KEY unique_member (group_id, user_id)
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS group_messages (
            id INT AUTO_INCREMENT PRIMARY KEY,
            group_id INT NOT NULL,
            sender_id INT NOT NULL,
            message TEXT NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (group_id) REFERENCES groups(id),
            FOREIGN KEY (sender_id) REFERENCES users(id)
        )
    """)
    
    #Normal read_receipts
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS read_receipts (
            id INT AUTO_INCREMENT PRIMARY KEY,
            message_id INT NOT NULL,
            reader_id INT NOT NULL,
            read_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (message_id) REFERENCES messages(id),
            FOREIGN KEY (reader_id) REFERENCES users(id),
            UNIQUE KEY unique_read (message_id, reader_id)
        )
    """)
    
    #group_read_receipts
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS group_read_receipts (
            id INT AUTO_INCREMENT PRIMARY KEY,
            message_id INT NOT NULL,
            reader_id INT NOT NULL,
            read_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (message_id) REFERENCES group_messages(id),
            FOREIGN KEY (reader_id) REFERENCES users(id),
            UNIQUE KEY unique_group_read (message_id, reader_id)
        )
    """)
    
    conn.commit()

async def handle_message(websocket, path):
    print("New client connected.")
    try:
        async for message in websocket:
            try:
                data = json.loads(message)
            except json.JSONDecodeError:
                await websocket.send(json.dumps({"status": "error", "message": "Invalid JSON."}))
                continue

            action = data.get("action")
            
            if action == "register":
                username = data.get("username")
                if not username:
                    response = {"status": "error", "message": "Username not provided."}
                else:
                    try:
                        cursor.execute("INSERT INTO users (username) VALUES (%s)", (username,))
                        conn.commit()
                        response = {"status": "ok", "message": f"User '{username}' registered successfully."}
                    except mysql.connector.Error as err:
                        response = {"status": "error", "message": f"Registration failed: {err.msg}"}
                await websocket.send(json.dumps(response))

            elif action == "send":
                sender = data.get("sender")
                receiver = data.get("receiver")
                msg_text = data.get("message")
                if not (sender and receiver and msg_text):
                    response = {"status": "error", "message": "Missing sender, receiver, or message text."}
                    await websocket.send(json.dumps(response))
                    continue

                cursor.execute("SELECT id FROM users WHERE username = %s", (sender,))
                sender_row = cursor.fetchone()
                cursor.execute("SELECT id FROM users WHERE username = %s", (receiver,))
                receiver_row = cursor.fetchone()
                if not sender_row:
                    response = {"status": "error", "message": f"Sender '{sender}' not found."}
                elif not receiver_row:
                    response = {"status": "error", "message": f"Receiver '{receiver}' not found."}
                else:
                    sender_id = sender_row[0]
                    receiver_id = receiver_row[0]
                    cursor.execute("SELECT id FROM userChats WHERE sender_id = %s AND receiver_id = %s", 
                                (sender_id, receiver_id))
                    chat_row = cursor.fetchone()
                    if chat_row:
                        chat_id = chat_row[0]
                    else:
                        cursor.execute("INSERT INTO userChats (sender_id, receiver_id) VALUES (%s, %s)",
                                    (sender_id, receiver_id))
                        conn.commit()
                        chat_id = cursor.lastrowid

                    cursor.execute("INSERT INTO messages (chat_id, sender_id, message) VALUES (%s, %s, %s)",
                                (chat_id, sender_id, msg_text))
                    conn.commit()
                    response = {"status": "ok", "message": "Message sent."}
                await websocket.send(json.dumps(response))

            elif action == "show":
                username = data.get("username")
                if not username:
                    response = {"status": "error", "message": "Username not provided."}
                else:
                    cursor.execute("SELECT id FROM users WHERE username = %s", (username,))
                    user_row = cursor.fetchone()
                    if not user_row:
                        response = {"status": "error", "message": f"User '{username}' not found."}
                    else:
                        user_id = user_row[0]
                        query = """
                            SELECT m.id, m.message, m.timestamp, u.username AS sender
                            FROM messages m
                            JOIN userChats uc ON m.chat_id = uc.id
                            JOIN users u ON m.sender_id = u.id
                            WHERE uc.receiver_id = %s OR (uc.sender_id = %s AND m.sender_id != %s)
                            ORDER BY m.timestamp ASC
                        """
                        cursor.execute(query, (user_id, user_id, user_id))
                        messages_list = cursor.fetchall()
                        messages_data = [
                            {"id": row[0], "message": row[1], "timestamp": str(row[2]), "sender": row[3]} 
                            for row in messages_list
                        ]
                        response = {"status": "ok", "messages": messages_data}
                await websocket.send(json.dumps(response))
            
            elif action == "mark_read":
                username = data.get("username")
                message_id = data.get("message_id")
                if not (username and message_id):
                    response = {"status": "error", "message": "Missing username or message ID."}
                else:
                    cursor.execute("SELECT id FROM users WHERE username = %s", (username,))
                    user_row = cursor.fetchone()
                    if not user_row:
                        response = {"status": "error", "message": f"User '{username}' not found."}
                    else:
                        user_id = user_row[0]
                        try:
                            #Check if message sent to this user 
                            cursor.execute("""
                                SELECT m.sender_id FROM messages m
                                JOIN userChats uc ON m.chat_id = uc.id
                                WHERE m.id = %s AND uc.receiver_id = %s AND m.sender_id != %s
                            """, (message_id, user_id, user_id))
                            message_check = cursor.fetchone()
                            
                            if message_check:
                                #Insert read receipt 
                                cursor.execute("""
                                    INSERT INTO read_receipts (message_id, reader_id)
                                    VALUES (%s, %s)
                                    ON DUPLICATE KEY UPDATE read_at = CURRENT_TIMESTAMP
                                """, (message_id, user_id))
                                conn.commit()
                                response = {"status": "ok", "message": "Message marked as read."}
                            else:
                                response = {"status": "error", "message": "Cannot mark this message as read."}
                        except mysql.connector.Error as err:
                            response = {"status": "error", "message": f"Failed to mark as read: {err.msg}"}
                await websocket.send(json.dumps(response))
            
            elif action == "read_status":
                username = data.get("username")
                if not username:
                    response = {"status": "error", "message": "Username not provided."}
                else:
                    cursor.execute("SELECT id FROM users WHERE username = %s", (username,))
                    user_row = cursor.fetchone()
                    if not user_row:
                        response = {"status": "error", "message": f"User '{username}' not found."}
                    else:
                        user_id = user_row[0]
                        query = """
                            SELECT r.message_id, u.username AS reader, r.read_at
                            FROM read_receipts r
                            JOIN users u ON r.reader_id = u.id
                            JOIN messages m ON r.message_id = m.id
                            WHERE m.sender_id = %s
                            ORDER BY r.read_at DESC
                        """
                        cursor.execute(query, (user_id,))
                        read_list = cursor.fetchall()
                        read_data = [
                            {"message_id": row[0], "reader": row[1], "read_at": str(row[2])}
                            for row in read_list
                        ]
                        response = {"status": "ok", "read_status": read_data}
                await websocket.send(json.dumps(response))
            
            
            elif action == "delete_message":
                username = data.get("username")
                message_id = data.get("message_id")
                if not (username and message_id):
                    response = {"status": "error", "message": "Missing username or message ID."}
                else:
                    cursor.execute("SELECT id FROM users WHERE username = %s", (username,))
                    user_row = cursor.fetchone()
                    if not user_row:
                        response = {"status": "error", "message": f"User '{username}' not found."}
                    else:
                        user_id = user_row[0]
                        
                        cursor.execute("SELECT sender_id FROM messages WHERE id = %s", (message_id,))
                        message_row = cursor.fetchone()
                        
                        if not message_row:
                            response = {"status": "error", "message": "Message not found."}
                        elif message_row[0] != user_id:
                            response = {"status": "error", "message": "You can only delete your own messages."}
                        else:
                            try:
                                cursor.execute("DELETE FROM read_receipts WHERE message_id = %s", (message_id,))
                                
                                cursor.execute("DELETE FROM messages WHERE id = %s", (message_id,))
                                
                                conn.commit()
                                
                                if cursor.rowcount > 0:
                                    response = {"status": "ok", "message": "Message deleted successfully."}
                                else:
                                    response = {"status": "error", "message": "Failed to delete message."}
                            except mysql.connector.Error as err:
                                response = {"status": "error", "message": f"Failed to delete message: {err.msg}"}
                await websocket.send(json.dumps(response))
            
            elif action == "create_group":
                group_name = data.get("group_name")
                creator = data.get("creator")
                if not (group_name and creator):
                    response = {"status": "error", "message": "Missing group name or creator."}
                else:
                    cursor.execute("SELECT id FROM users WHERE username = %s", (creator,))
                    creator_row = cursor.fetchone()
                    if not creator_row:
                        response = {"status": "error", "message": f"User '{creator}' not found."}
                    else:
                        creator_id = creator_row[0]
                        try:
                            cursor.execute("INSERT INTO groups (name, created_by) VALUES (%s, %s)", 
                                        (group_name, creator_id))
                            group_id = cursor.lastrowid

                            cursor.execute("INSERT INTO group_members (group_id, user_id) VALUES (%s, %s)",
                                        (group_id, creator_id))
                            conn.commit()
                            response = {"status": "ok", "message": f"Group '{group_name}' created successfully."}
                        except mysql.connector.Error as err:
                            response = {"status": "error", "message": f"Group creation failed: {err.msg}"}
                await websocket.send(json.dumps(response))
            
            elif action == "add_member":
                group_name = data.get("group_name")
                username = data.get("username")
                adder = data.get("adder") 
                if not (group_name and username and adder):
                    response = {"status": "error", "message": "Missing group name, username, or adder."}
                else:
                    cursor.execute("SELECT id FROM groups WHERE name = %s", (group_name,))
                    group_row = cursor.fetchone()
                    if not group_row:
                        response = {"status": "error", "message": f"Group '{group_name}' not found."}
                    else:
                        group_id = group_row[0]
                        
                        cursor.execute("SELECT u.id FROM users u JOIN group_members gm ON u.id = gm.user_id WHERE u.username = %s AND gm.group_id = %s", 
                                    (adder, group_id))
                        adder_row = cursor.fetchone()
                        if not adder_row:
                            response = {"status": "error", "message": f"User '{adder}' is not a member of this group."}
                        else:

                            cursor.execute("SELECT id FROM users WHERE username = %s", (username,))
                            user_row = cursor.fetchone()
                            if not user_row:
                                response = {"status": "error", "message": f"User '{username}' not found."}
                            else:
                                user_id = user_row[0]
                                try:
                                    cursor.execute("INSERT INTO group_members (group_id, user_id) VALUES (%s, %s)",
                                                (group_id, user_id))
                                    conn.commit()
                                    response = {"status": "ok", "message": f"User '{username}' added to group '{group_name}' successfully."}
                                except mysql.connector.Error as err:
                                    if err.errno == 1062:  
                                        response = {"status": "error", "message": f"User '{username}' is already a member of this group."}
                                    else:
                                        response = {"status": "error", "message": f"Failed to add member: {err.msg}"}
                await websocket.send(json.dumps(response))
            
            elif action == "list_groups":
                username = data.get("username")
                if not username:
                    response = {"status": "error", "message": "Username not provided."}
                else:
                    cursor.execute("SELECT id FROM users WHERE username = %s", (username,))
                    user_row = cursor.fetchone()
                    if not user_row:
                        response = {"status": "error", "message": f"User '{username}' not found."}
                    else:
                        user_id = user_row[0]
                        query = """
                            SELECT g.id, g.name, g.created_at, COUNT(gm.user_id) as member_count
                            FROM groups g
                            JOIN group_members gm ON g.id = gm.group_id
                            WHERE EXISTS (
                                SELECT 1 FROM group_members 
                                WHERE group_id = g.id AND user_id = %s
                            )
                            GROUP BY g.id
                            ORDER BY g.created_at DESC
                        """
                        cursor.execute(query, (user_id,))
                        groups_list = cursor.fetchall()
                        groups_data = [
                            {"id": row[0], "name": row[1], "created_at": str(row[2]), "member_count": row[3]} 
                            for row in groups_list
                        ]
                        response = {"status": "ok", "groups": groups_data}
                await websocket.send(json.dumps(response))
            
            elif action == "list_members":
                group_name = data.get("group_name")
                if not group_name:
                    response = {"status": "error", "message": "Group name not provided."}
                else:
                    cursor.execute("SELECT id FROM groups WHERE name = %s", (group_name,))
                    group_row = cursor.fetchone()
                    if not group_row:
                        response = {"status": "error", "message": f"Group '{group_name}' not found."}
                    else:
                        group_id = group_row[0]
                        query = """
                            SELECT u.username, gm.joined_at, 
                            (SELECT username FROM users WHERE id = g.created_by) as created_by
                            FROM group_members gm
                            JOIN users u ON gm.user_id = u.id
                            JOIN groups g ON gm.group_id = g.id
                            WHERE gm.group_id = %s
                            ORDER BY gm.joined_at ASC
                        """
                        cursor.execute(query, (group_id,))
                        members_list = cursor.fetchall()
                        members_data = [
                            {"username": row[0], "joined_at": str(row[1]), "is_admin": (row[0] == row[2])} 
                            for row in members_list
                        ]
                        response = {"status": "ok", "members": members_data}
                await websocket.send(json.dumps(response))
            
            elif action == "send_group_message":
                sender = data.get("sender")
                group_name = data.get("group_name")
                msg_text = data.get("message")
                if not (sender and group_name and msg_text):
                    response = {"status": "error", "message": "Missing sender, group name, or message text."}
                else:
                    cursor.execute("SELECT id FROM users WHERE username = %s", (sender,))
                    sender_row = cursor.fetchone()
                    cursor.execute("SELECT id FROM groups WHERE name = %s", (group_name,))
                    group_row = cursor.fetchone()
                    
                    if not sender_row:
                        response = {"status": "error", "message": f"Sender '{sender}' not found."}
                    elif not group_row:
                        response = {"status": "error", "message": f"Group '{group_name}' not found."}
                    else:
                        sender_id = sender_row[0]
                        group_id = group_row[0]
                        
                        cursor.execute("SELECT 1 FROM group_members WHERE group_id = %s AND user_id = %s",
                                    (group_id, sender_id))
                        is_member = cursor.fetchone()
                        if not is_member:
                            response = {"status": "error", "message": f"User '{sender}' is not a member of this group."}
                        else:
                            cursor.execute("INSERT INTO group_messages (group_id, sender_id, message) VALUES (%s, %s, %s)",
                                        (group_id, sender_id, msg_text))
                            conn.commit()
                            response = {"status": "ok", "message": "Group message sent."}
                await websocket.send(json.dumps(response))
            
            elif action == "show_group_messages":
                group_name = data.get("group_name")
                username = data.get("username")
                if not (group_name and username):
                    response = {"status": "error", "message": "Missing group name or username."}
                else:
                    cursor.execute("SELECT id FROM groups WHERE name = %s", (group_name,))
                    group_row = cursor.fetchone()
                    cursor.execute("SELECT id FROM users WHERE username = %s", (username,))
                    user_row = cursor.fetchone()
                    
                    if not group_row:
                        response = {"status": "error", "message": f"Group '{group_name}' not found."}
                    elif not user_row:
                        response = {"status": "error", "message": f"User '{username}' not found."}
                    else:
                        group_id = group_row[0]
                        user_id = user_row[0]
                        
                        cursor.execute("SELECT 1 FROM group_members WHERE group_id = %s AND user_id = %s",
                                    (group_id, user_id))
                        is_member = cursor.fetchone()
                        if not is_member:
                            response = {"status": "error", "message": f"User '{username}' is not a member of this group."}
                        else:
                            query = """
                                SELECT gm.id, gm.message, gm.timestamp, u.username AS sender
                                FROM group_messages gm
                                JOIN users u ON gm.sender_id = u.id
                                WHERE gm.group_id = %s
                                ORDER BY gm.timestamp ASC
                            """
                            cursor.execute(query, (group_id,))
                            messages_list = cursor.fetchall()
                            messages_data = [
                                {"id": row[0], "sender": row[3], "message": row[1], "timestamp": str(row[2])} 
                                for row in messages_list
                            ]
                            
                            for msg in messages_list:
                                if msg[3] != username:  
                                    try:
                                        cursor.execute("""
                                            INSERT INTO group_read_receipts (message_id, reader_id)
                                            VALUES (%s, %s)
                                            ON DUPLICATE KEY UPDATE read_at = CURRENT_TIMESTAMP
                                        """, (msg[0], user_id))
                                    except mysql.connector.Error:
                                        pass  
                            conn.commit()
                            
                            response = {"status": "ok", "messages": messages_data}
                await websocket.send(json.dumps(response))
            
            elif action == "delete_group_message":
                username = data.get("username")
                message_id = data.get("message_id")
                if not (username and message_id):
                    response = {"status": "error", "message": "Missing username or message ID."}
                else:
                    cursor.execute("SELECT id FROM users WHERE username = %s", (username,))
                    user_row = cursor.fetchone()
                    if not user_row:
                        response = {"status": "error", "message": f"User '{username}' not found."}
                    else:
                        user_id = user_row[0]
                        
                        cursor.execute("""
                            SELECT gm.sender_id, gm.group_id, g.created_by 
                            FROM group_messages gm
                            JOIN groups g ON gm.group_id = g.id
                            WHERE gm.id = %s
                        """, (message_id,))
                        message_row = cursor.fetchone()
                        
                        if not message_row:
                            response = {"status": "error", "message": "Group message not found."}
                        elif message_row[0] != user_id and message_row[2] != user_id:
                            response = {"status": "error", "message": "You can only delete your own messages or messages in groups you created."}
                        else:
                            try:
                                cursor.execute("DELETE FROM group_read_receipts WHERE message_id = %s", (message_id,))
                                
                                cursor.execute("DELETE FROM group_messages WHERE id = %s", (message_id,))
                                
                                conn.commit()
                                
                                if cursor.rowcount > 0:
                                    response = {"status": "ok", "message": "Group message deleted successfully."}
                                else:
                                    response = {"status": "error", "message": "Failed to delete group message."}
                            except mysql.connector.Error as err:
                                response = {"status": "error", "message": f"Failed to delete group message: {err.msg}"}
                await websocket.send(json.dumps(response))
            
            elif action == "leave_group":
                username = data.get("username")
                group_name = data.get("group_name")
                if not (username and group_name):
                    response = {"status": "error", "message": "Missing username or group name."}
                else:
                    cursor.execute("SELECT id FROM users WHERE username = %s", (username,))
                    user_row = cursor.fetchone()
                    cursor.execute("SELECT id FROM groups WHERE name = %s", (group_name,))
                    group_row = cursor.fetchone()
                    
                    if not user_row:
                        response = {"status": "error", "message": f"User '{username}' not found."}
                    elif not group_row:
                        response = {"status": "error", "message": f"Group '{group_name}' not found."}
                    else:
                        user_id = user_row[0]
                        group_id = group_row[0]
                        
                        cursor.execute("SELECT created_by FROM groups WHERE id = %s", (group_id,))
                        creator_id = cursor.fetchone()[0]
                        if creator_id == user_id:
                            response = {"status": "error", "message": "Group creator cannot leave. You must delete the group instead."}
                        else:
                            cursor.execute("DELETE FROM group_members WHERE group_id = %s AND user_id = %s",
                                        (group_id, user_id))
                            conn.commit()
                            if cursor.rowcount > 0:
                                response = {"status": "ok", "message": f"Successfully left group '{group_name}'."}
                            else:
                                response = {"status": "error", "message": f"User '{username}' is not a member of this group."}
                await websocket.send(json.dumps(response))
                
            elif action == "group_read_status":
                message_id = data.get("message_id")
                if not message_id:
                    response = {"status": "error", "message": "Message ID not provided."}
                else:
                    query = """
                        SELECT u.username, gr.read_at
                        FROM group_read_receipts gr
                        JOIN users u ON gr.reader_id = u.id
                        WHERE gr.message_id = %s
                        ORDER BY gr.read_at ASC
                    """
                    cursor.execute(query, (message_id,))
                    readers = cursor.fetchall()
                    readers_data = [
                        {"username": row[0], "read_at": str(row[1])}
                        for row in readers
                    ]
                    
                    query = """
                        SELECT u.username
                        FROM group_members gm
                        JOIN users u ON gm.user_id = u.id
                        JOIN group_messages gms ON gms.group_id = gm.group_id
                        WHERE gms.id = %s
                        AND NOT EXISTS (
                            SELECT 1 FROM group_read_receipts gr 
                            WHERE gr.message_id = %s AND gr.reader_id = gm.user_id
                        )
                        AND gm.user_id != (SELECT sender_id FROM group_messages WHERE id = %s)
                    """
                    cursor.execute(query, (message_id, message_id, message_id))
                    unread = cursor.fetchall()
                    unread_data = [row[0] for row in unread]
                    
                    response = {
                        "status": "ok", 
                        "read_by": readers_data,
                        "not_read_by": unread_data
                    }
                await websocket.send(json.dumps(response))
            
            else:
                response = {"status": "error", "message": "Unknown action."}
                await websocket.send(json.dumps(response))
    except websockets.exceptions.ConnectionClosed:
        print("Client disconnected.")

if __name__ == "__main__":
    setup_database()
    
    start_server = websockets.serve(handle_message, "localhost", 8765)
    print("Server started on ws://localhost:8765")
    
    asyncio.get_event_loop().run_until_complete(start_server)
    asyncio.get_event_loop().run_forever()