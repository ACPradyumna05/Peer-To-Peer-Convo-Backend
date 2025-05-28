import asyncio
import websockets
import json
import os
from datetime import datetime

async def chat_client():
    uri = "ws://localhost:8765"
    async with websockets.connect(uri) as websocket:
        print("\n===== Welcome to the Chat System =====")
        print("=" * 35)
        username = input("Enter your username to register/login: ").strip()
        
        reg_msg = {"action": "register", "username": username}
        await websocket.send(json.dumps(reg_msg))
        response = json.loads(await websocket.recv())
        print(response.get("message"))
        
        while True:
            print("\n==== MAIN MENU ====")
            print("1. Personal Chat")
            print("2. Group Chat")
            print("3. Quit")
            
            main_choice = input("\nEnter choice (1/2/3): ").strip()
            
            if main_choice == "1":
                #Personal chat menu
                await personal_chat_menu(websocket, username)
            
            elif main_choice == "2":
                #Group chat menu
                await group_chat_menu(websocket, username)
            
            elif main_choice == "3":
                print("Exiting the chat system. Goodbye!")
                break
            
            else:
                print("Invalid choice. Please select 1, 2, or 3.")

async def personal_chat_menu(websocket, username):
    while True:
        print("\n==== PERSONAL CHAT ====")
        print("1. Send a message")
        print("2. Show received messages")
        print("3. Check read status of your messages")
        print("4. Delete a message")
        print("5. Back to main menu")
        
        choice = input("\nEnter choice (1-5): ").strip()
        
        if choice == "1":
            receiver = input("Enter receiver's username: ").strip()
            message_text = input("Enter your message: ").strip()
            send_msg = {
                "action": "send",
                "sender": username,
                "receiver": receiver,
                "message": message_text
            }
            await websocket.send(json.dumps(send_msg))
            response = json.loads(await websocket.recv())
            print(response.get("message"))
        
        elif choice == "2":
            show_msg = {"action": "show", "username": username}
            await websocket.send(json.dumps(show_msg))
            response = json.loads(await websocket.recv())
            if response.get("status") == "ok":
                messages = response.get("messages")
                if messages:
                    print("\n=== Received Messages ===")
                    for m in messages:
                        print(f"[{m['timestamp']}] {m['sender']}: {m['message']} (ID: {m['id']})")
                        
                        if m['sender'] != username:
                            mark_read_msg = {
                                "action": "mark_read",
                                "username": username,
                                "message_id": m['id']
                            }
                            await websocket.send(json.dumps(mark_read_msg))
                            await websocket.recv()
                            
                    print("=" * 25)
                else:
                    print("No messages received.")
            else:
                print(response.get("message"))
        
        elif choice == "3":

            read_status_msg = {
                "action": "read_status",
                "username": username
            }
            await websocket.send(json.dumps(read_status_msg))
            response = json.loads(await websocket.recv())
            
            if response.get("status") == "ok":
                read_data = response.get("read_status")
                if read_data:
                    print("\n=== Read Receipts for Your Messages ===")
                    print(f"{'Message ID':<10} {'Read By':<20} {'Read At':<25}")
                    print("-" * 55)
                    for r in read_data:
                        print(f"{r['message_id']:<10} {r['reader']:<20} {r['read_at']:<25}")
                    print("=" * 55)
                else:
                    print("None of your messages have been read yet.")
            else:
                print(response.get("message"))
        
        elif choice == "4":
            message_id = input("Enter message ID to delete: ").strip()
            try:
                message_id = int(message_id)
                confirm = input(f"Are you sure you want to delete message ID {message_id}? (y/n): ").strip().lower()
                
                if confirm == 'y':
                    delete_msg = {
                        "action": "delete_message",
                        "username": username,
                        "message_id": message_id
                    }
                    await websocket.send(json.dumps(delete_msg))
                    response = json.loads(await websocket.recv())
                    print(response.get("message"))
                else:
                    print("Message deletion cancelled.")
            except ValueError:
                print("Message ID must be a number.")
        
        elif choice == "5":
            return
        
        else:
            print("Invalid choice. Please select 1-5.")

async def group_chat_menu(websocket, username):
    while True:
        print("\n==== GROUP CHAT ====")
        print("1. Create new group")
        print("2. View my groups")
        print("3. Send message to group")
        print("4. Show group messages")
        print("5. Add member to group")
        print("6. View group members")
        print("7. Leave a group")
        print("8. Check message read status")
        print("9. Delete group message")
        print("10. Back to main menu")
        
        choice = input("\nEnter choice (1-10): ").strip()
        
        if choice == "1":
            # Create new group
            group_name = input("Enter group name: ").strip()
            if not group_name:
                print("Group name cannot be empty.")
                continue
                
            create_msg = {
                "action": "create_group",
                "group_name": group_name,
                "creator": username
            }
            await websocket.send(json.dumps(create_msg))
            response = json.loads(await websocket.recv())
            print(response.get("message"))
        
        elif choice == "2":

            list_msg = {
                "action": "list_groups",
                "username": username
            }
            await websocket.send(json.dumps(list_msg))
            response = json.loads(await websocket.recv())
            
            if response.get("status") == "ok":
                groups = response.get("groups")
                if groups:
                    print("\n=== Your Groups ===")
                    print(f"{'Name':<20} {'Created At':<25} {'Members':<10}")
                    print("-" * 55)
                    for g in groups:
                        print(f"{g['name']:<20} {g['created_at']:<25} {g['member_count']:<10}")
                    print("=" * 55)
                else:
                    print("You are not a member of any groups.")
            else:
                print(response.get("message"))
        
        elif choice == "3":

            group_name = input("Enter group name: ").strip()
            message_text = input("Enter your message: ").strip()
            
            send_msg = {
                "action": "send_group_message",
                "sender": username,
                "group_name": group_name,
                "message": message_text
            }
            await websocket.send(json.dumps(send_msg))
            response = json.loads(await websocket.recv())
            print(response.get("message"))
        
        elif choice == "4":

            group_name = input("Enter group name: ").strip()
            
            show_msg = {
                "action": "show_group_messages",
                "username": username,
                "group_name": group_name
            }
            await websocket.send(json.dumps(show_msg))
            response = json.loads(await websocket.recv())
            
            if response.get("status") == "ok":
                messages = response.get("messages")
                if messages:
                    os.system('cls' if os.name == 'nt' else 'clear')
                    print(f"\n=== Messages in Group: {group_name} ===")
                    for m in messages:
                        timestamp = m['timestamp']
                        print(f"[{timestamp}] {m['sender']}: {m['message']} (ID: {m['id']})")
                    print("=" * 40)
                    print("Note: All messages from others are automatically marked as read")
                    input("Press Enter to continue...")
                else:
                    print(f"No messages in group '{group_name}'.")
            else:
                print(response.get("message"))
        
        elif choice == "5":

            group_name = input("Enter group name: ").strip()
            new_member = input("Enter username to add: ").strip()
            
            add_msg = {
                "action": "add_member",
                "group_name": group_name,
                "username": new_member,
                "adder": username
            }
            await websocket.send(json.dumps(add_msg))
            response = json.loads(await websocket.recv())
            print(response.get("message"))
        
        elif choice == "6":

            group_name = input("Enter group name: ").strip()
            
            list_msg = {
                "action": "list_members",
                "group_name": group_name
            }
            await websocket.send(json.dumps(list_msg))
            response = json.loads(await websocket.recv())
            
            if response.get("status") == "ok":
                members = response.get("members")
                if members:
                    print(f"\n=== Members in Group: {group_name} ===")
                    print(f"{'Username':<20} {'Joined At':<25} {'Role':<10}")
                    print("-" * 55)
                    for m in members:
                        role = "Admin" if m['is_admin'] else "Member"
                        print(f"{m['username']:<20} {m['joined_at']:<25} {role:<10}")
                    print("=" * 55)
                else:
                    print(f"No members in group '{group_name}'.")
            else:
                print(response.get("message"))
        
        elif choice == "7":

            group_name = input("Enter name of group to leave: ").strip()
            confirm = input(f"Are you sure you want to leave '{group_name}'? (y/n): ").strip().lower()
            
            if confirm == 'y':
                leave_msg = {
                    "action": "leave_group",
                    "username": username,
                    "group_name": group_name
                }
                await websocket.send(json.dumps(leave_msg))
                response = json.loads(await websocket.recv())
                print(response.get("message"))
        
        elif choice == "8":

            message_id = input("Enter message ID to check: ").strip()
            try:
                message_id = int(message_id)
                
                check_msg = {
                    "action": "group_read_status",
                    "message_id": message_id
                }
                await websocket.send(json.dumps(check_msg))
                response = json.loads(await websocket.recv())
                
                if response.get("status") == "ok":
                    read_list = response.get("read_by")
                    unread_list = response.get("not_read_by")
                    
                    print("\n=== Message Read Status ===")
                    if read_list:
                        print("\nRead by:")
                        print(f"{'Username':<20} {'Read At':<25}")
                        print("-" * 45)
                        for r in read_list:
                            print(f"{r['username']:<20} {r['read_at']:<25}")
                    
                    if unread_list:
                        print("\nNot read by:")
                        for username in unread_list:
                            print(f"- {username}")
                    
                    if not read_list and not unread_list:
                        print("No read receipt data available for this message.")
                        
                    print("=" * 45)
                else:
                    print(response.get("message"))
            except ValueError:
                print("Message ID must be a number.")
        
        elif choice == "9":

            message_id = input("Enter group message ID to delete: ").strip()
            try:
                message_id = int(message_id)
                confirm = input(f"Are you sure you want to delete group message ID {message_id}? (y/n): ").strip().lower()
                
                if confirm == 'y':
                    delete_msg = {
                        "action": "delete_group_message",
                        "username": username,
                        "message_id": message_id
                    }
                    await websocket.send(json.dumps(delete_msg))
                    response = json.loads(await websocket.recv())
                    print(response.get("message"))
                else:
                    print("Group message deletion cancelled.")
            except ValueError:
                print("Message ID must be a number.")
        
        elif choice == "10":
            return
        
        else:
            print("Invalid choice. Please select 1-10.")

if __name__ == "__main__":
    try:
        asyncio.run(chat_client())
    except KeyboardInterrupt:
        print("\nForced exit by user. Goodbye!")
    except Exception as e:
        print(f"\nAn error occurred: {e}")