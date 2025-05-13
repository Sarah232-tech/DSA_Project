import tkinter as tk
from tkinter import messagebox, ttk, simpledialog, filedialog
from datetime import datetime, timedelta
import json
import os
import tempfile
from PIL import Image, ImageTk
from dateutil import parser
import matplotlib.pyplot as plt
from collections import Counter

# --- File paths ---

DATA_FILE   = 'inventory_data.json'        # Inventory data storage
SALES_FILE  = 'sales_history.json'         # Sales history data storage
USERS_FILE  = 'users.json'                 # User credentials storage
LOW_STOCK_THRESHOLD = 5                    # Threshold for low stock alert
ICON_DIR    = 'icons'                      # Directory where icons are stored

# --- Data persistence ---

def load_json(path, default):
    # Load data from a JSON file, or return default if file doesn't exist
    if os.path.exists(path):
        with open(path, 'r') as f:
            return json.load(f)
    return default

def save_json(path, data):
    # Save data to a JSON file
    with open(path, 'w') as f:
        json.dump(data, f, indent=4)

# Load existing data from files or use default
inventory     = load_json(DATA_FILE, {})
sales_history = load_json(SALES_FILE, [])
USERS         = load_json(USERS_FILE, {})

# --- Login window ---

def login_window(on_success):
    # Create the login window
    win = tk.Tk()
    win.title("Login")
    win.geometry("400x450")
    win.configure(bg="#5F9EA0")

    # Header label
    tk.Label(
        win, text="Login to Inventory System", font=("Helvetica", 18, "bold"),
        fg="dark blue", bg="#e6f2ff", padx=20, pady=10, bd=4, relief="groove"
    ).pack(pady=(30, 20))

    # Username input
    tk.Label(win, text="Username", bg="#f0f0f0", font=("Arial", 12)).pack(pady=(10, 0))
    user_ent = tk.Entry(win); user_ent.pack()

    # Password input
    tk.Label(win, text="Password", bg="#f0f0f0", font=("Arial", 12)).pack(pady=(10, 0))
    pwd_ent  = tk.Entry(win, show='*'); pwd_ent.pack()

    # Function for login button
    def do_login():
        u, p = user_ent.get(), pwd_ent.get()
        if USERS.get(u) == p:
            win.destroy()
            on_success()
        else:
            messagebox.showerror("Login Failed", "Invalid credentials")

    # Function for register button
    def do_register():
        u = simpledialog.askstring("Register", "Username:")
        p = simpledialog.askstring("Register", "Password:", show='*')
        if u and p and u not in USERS:
            USERS[u] = p
            save_json(USERS_FILE, USERS)
            messagebox.showinfo("Success", "Registered")
        else:
            messagebox.showerror("Error", "Invalid or existing user")

    # Function for password reset
    def do_reset():
        u = simpledialog.askstring("Reset Password", "Username:")
        if u in USERS:
            p = simpledialog.askstring("Reset Password", "New password:", show='*')
            USERS[u] = p
            save_json(USERS_FILE, USERS)
            messagebox.showinfo("Success", "Password reset")
        else:
            messagebox.showerror("Error", "User not found")

    # Create login, register, and reset buttons
    for txt, cmd in [
        ("Login", do_login),
        ("Register", do_register),
        ("Forgot Password", do_reset)
    ]:
        tk.Button(
            win, text=txt, width=15, bg="#d9f0ff", fg="dark blue", activebackground="#45a049",
            font=("Arial", 12, "bold"), pady=4, command=cmd
        ).pack(pady=5)

    win.mainloop()

# --- Modal dialog helper ---

class ModalDialog:
    def __init__(self, parent, title, fields):
        # Create a popup modal dialog window for user input
        self.top = tk.Toplevel(parent)
        self.top.title(title)
        self.entries = {}
        for i, spec in enumerate(fields):
            label, typ = spec[0], spec[1]
            show = '*' if len(spec) > 2 and spec[2] else None
            tk.Label(self.top, text=label).grid(row=i, column=0, padx=10, pady=5, sticky="e")
            ent = tk.Entry(self.top, show=show)
            ent.grid(row=i, column=1, padx=10, pady=5)
            self.entries[label] = (ent, typ)
        tk.Button(self.top, text="OK", command=self._on_ok).grid(
            row=len(fields), column=0, columnspan=2, pady=10
        )
        self.value = None
        self.top.grab_set()
        parent.wait_window(self.top)

    def _on_ok(self):
        # Gather user input and close dialog if valid
        res = {}
        try:
            for label, (ent, typ) in self.entries.items():
                txt = ent.get().strip()
                if typ is int:
                    res[label] = int(txt)
                elif typ is float:
                    res[label] = float(txt)
                else:
                    res[label] = txt
        except ValueError:
            messagebox.showerror("Error", "Please enter valid values")
            return
        self.value = res
        self.top.destroy()

    def result(self):
        # Return collected input values
        return self.value
    
    
    
class InventorySystem:
    def __init__(self):
        # Initialize sale-related variables
        self.current_sale = {}   # Tracks items currently being added to a sale
        self.last_receipt  = ""  # Stores last receipt content as string

        # Set up the main application window
        self.root = tk.Tk()
        self.root.title("Inventory Management System")
        self.root.geometry("800x600")

        # Load all icons from ICON_DIR folder for buttons
        self.icons = {}
        for name in [
            'view','add','update','delete','search','charts','reports','incoming','outgoing',
            'sale_add','sale_complete','sale_history','sale_print'
        ]:
            img_obj = None
            for ext in ('.png','.jpg','.jpeg'):  # Try supported extensions
                path = os.path.join(ICON_DIR, name + ext)
                if os.path.exists(path):
                    try:
                        img = Image.open(path).convert("RGB").resize((24, 24))  # Resize and format
                        img_obj = ImageTk.PhotoImage(img)
                    except Exception as e:
                        print(f"Error loading {path}: {e}")
                    break
            self.icons[name] = img_obj  # Save icon image or None if not found

        # Create tabbed interface with two tabs: Owner and Sales
        nb = ttk.Notebook(self.root)
        self.frame_owner = tk.Frame(nb)
        self.frame_sales = tk.Frame(nb)
        nb.add(self.frame_owner, text="Shop Owner")
        nb.add(self.frame_sales, text="Sales")
        nb.pack(expand=True, fill="both")

        # Build each tab's layout
        self._build_owner_page()
        self._build_sales_page()

        # Start the application main loop
        self.root.mainloop()

    # ---------------------- Owner Page Layout ---------------------- #
    def _build_owner_page(self):
        # Set background and header label
        self.frame_owner.configure(bg="#5F9EA0")
        tk.Label(
            self.frame_owner,
            text="Shop Owner Dashboard",
            font=("Helvetica", 18, "bold"),
            fg="dark blue",
            bg="#e6f2ff",
            padx=20,
            pady=10,
            bd=4,
            relief="groove"
        ).pack(pady=15, fill='x')

        # Define owner-side actions and icons
        btns = [
            ('view','View Items',    self._view_inventory),
            ('add', 'Add Item',      self._add_item),
            ('update','Update Item', self._update_item),
            ('delete','Delete Item', self._delete_item),
            ('search','Search',      self._search_item),
            ('charts','Charts',      self._show_charts),
            ('reports','Reports',    self._sales_report),
            ('incoming','➕ Incoming',   self._incoming_stock),
            ('outgoing','➖ Outgoing',   self._outgoing_stock),
        ]
        frm = tk.Frame(self.frame_owner, bg="#5F9EA0")
        frm.pack(pady=20)

        # Create buttons in a grid
        for i, (icon_key, txt, cmd) in enumerate(btns):
            ico = self.icons.get(icon_key)
            btn = tk.Button(frm, text=txt, image=ico, compound='left',
                            command=cmd,
                            width=160, height=100, bg="#d9f0ff", fg="dark blue",
                            activebackground="#45a049",
                            relief="raised", font=("Arial", 10, "bold"), padx=5, pady=5)
            btn.image = ico  # Keep a reference to avoid garbage collection
            btn.grid(row=i//3, column=i%3, padx=10, pady=10)

        # Check and alert if low stock exists
        self._low_stock_check()

    # ---------------------- Sales Page Layout ---------------------- #
    def _build_sales_page(self):
        # Set background and header label
        self.frame_sales.configure(bg="#5F9EA0")
        tk.Label(
            self.frame_sales,
            text="Sales Dashboard",
            font=("Helvetica", 18, "bold"),
            fg="dark blue",
            bg="#e6f2ff",
            padx=20,
            pady=10,
            bd=4,
            relief="groove"
        ).pack(pady=15, fill='x')

        # Define sales actions and icons
        actions = [
            ('sale_add',     'Add to Sale',    self._add_to_sale),
            ('sale_complete','Complete Sale',  self._complete_sale),
            ('sale_history','Sales History',   self._view_sales_history),
            ('sale_print',  'Print Receipt',   self._print_receipt),
        ]
        frm = tk.Frame(self.frame_sales, bg="#5F9EA0")
        frm.pack(pady=20)

        # Create buttons for sales actions
        for i, (icon_key, txt, cmd) in enumerate(actions):
            ico = self.icons.get(icon_key)
            btn = tk.Button(frm, text=txt, image=ico, compound='left',
                            command=cmd,
                            width=160, height=180, bg="#d9f0ff", fg="dark blue",
                            activebackground="#1976D2",
                            relief="raised", font=("Arial", 10, "bold"), padx=5, pady=5)
            btn.image = ico
            btn.grid(row=i//2, column=i%2, padx=10, pady=10)

        # Display the current inventory in a new top-level window using a Treeview widget
    def _view_inventory(self):
        top = tk.Toplevel(self.root)
        top.title("Current Inventory")
        tree = ttk.Treeview(top, columns=("ID","Name","Qty","Price"), show="headings")
        for c in (["ID","Name","Qty","Price"]):
            tree.heading(c, text=c)
            tree.column(c, anchor="center")
        tree.pack(expand=True, fill="both", padx=10, pady=10)
        for i, it in inventory.items():
            tree.insert("", "end", values=(i, it.get("name",""), it.get("quantity",0), it.get("price",0.0)))

    # Add a new item to the inventory after checking for ID uniqueness
    def _add_item(self):
        dlg = ModalDialog(self.root, "Add Item", [("ID",str),("Name",str),("Quantity",int),("Price",float)])
        r = dlg.result()
        if not r: return
        i,n,q,p = r["ID"], r["Name"], r["Quantity"], r["Price"]
        if i in inventory:
            messagebox.showerror("Error", "ID exists")
        else:
            inventory[i] = {"name":n, "quantity":q, "price":p}
            save_json(DATA_FILE, inventory)
            messagebox.showinfo("Success","Item added")
            self._low_stock_check()

    # Update an existing inventory item's details
    def _update_item(self):
        dlg = ModalDialog(self.root, "Update Item", [("ID",str)])
        r = dlg.result()
        if not r: return
        i = r["ID"]
        itm = inventory.get(i)
        if not itm:
            messagebox.showerror("Error","Not found"); return
        dlg2 = ModalDialog(self.root, "Update Item", [("Name",str),("Quantity",int),("Price",float)])
        r2 = dlg2.result()
        if not r2: return
        itm["name"], itm["quantity"], itm["price"] = r2["Name"], r2["Quantity"], r2["Price"]
        save_json(DATA_FILE, inventory)
        messagebox.showinfo("Success","Item updated")
        self._low_stock_check()

    # Delete an item from the inventory using its ID
    def _delete_item(self):
        dlg = ModalDialog(self.root, "Delete Item", [("ID",str)])
        r = dlg.result()
        if not r: return
        i = r["ID"]
        if i in inventory:
            del inventory[i]
            save_json(DATA_FILE, inventory)
            messagebox.showinfo("Success","Item deleted")
        else:
            messagebox.showerror("Error","Not found")

    # Search inventory items by ID or name and show results in a new window
    def _search_item(self):
        dlg = ModalDialog(self.root, "Search", [("Query",str)])
        r = dlg.result()
        if not r: return
        q = r["Query"].lower()
        results = [(i,it) for i,it in inventory.items()
                   if q in i.lower() or q in it.get("name","").lower()]
        top = tk.Toplevel(self.root)
        top.title(f"Search: {r['Query']}")
        tree = ttk.Treeview(top, columns=("ID","Name","Qty","Price"), show="headings")
        for c in ("ID","Name","Qty","Price"):
            tree.heading(c, text=c)
            tree.column(c, anchor="center")
        tree.pack(expand=True, fill="both", padx=10, pady=10)
        for i,it in results:
            tree.insert("", "end", values=(
                i,
                it.get("name",""),
                it.get("quantity",0),
                it.get("price",0.0)
            ))

    # Add incoming stock quantity to an existing inventory item
    def _incoming_stock(self):
        dlg = ModalDialog(self.root, "Incoming Stock", [("ID",str),("Quantity",int)])
        r = dlg.result()
        if not r: return
        i,q = r["ID"], r["Quantity"]
        if i in inventory:
            inventory[i]["quantity"] = inventory[i].get("quantity",0) + q
            save_json(DATA_FILE, inventory)
            messagebox.showinfo("Success","Stock updated")
            self._low_stock_check()
        else:
            messagebox.showerror("Error","Invalid ID")

    # Subtract outgoing stock quantity from an inventory item
    def _outgoing_stock(self):
        dlg = ModalDialog(self.root, "Outgoing Stock", [("ID",str),("Quantity",int)])
        r = dlg.result()
        if not r: return
        i,q = r["ID"], r["Quantity"]
        if i in inventory and inventory[i].get("quantity",0) >= q:
            inventory[i]["quantity"] -= q
            save_json(DATA_FILE, inventory)
            messagebox.showinfo("Success","Stock updated")
            self._low_stock_check()
        else:
            messagebox.showerror("Error","Invalid ID or insufficient stock")

    # Show a bar chart of all inventory item quantities using matplotlib
    def _show_charts(self):
        names = [it.get("name","") for it in inventory.values()]
        qtys  = [it.get("quantity",0) for it in inventory.values()]
        plt.bar(names, qtys)
        plt.xticks(rotation=45)
        plt.title("Inventory Levels")
        plt.ylabel("Quantity")
        plt.tight_layout()
        plt.show()

    # Generate a sales report between two dates, showing summary and individual sales
    def _sales_report(self):
        dlg = ModalDialog(self.root, "Generate Report", [
            ("Start Date (YYYY-MM-DD)", str),
            ("End Date (YYYY-MM-DD)",   str)
        ])
        r = dlg.result()
        if not r: return
        try:
            sd = datetime.strptime(r["Start Date (YYYY-MM-DD)"], "%Y-%m-%d")
            ed = datetime.strptime(r["End Date (YYYY-MM-DD)"],   "%Y-%m-%d") + timedelta(days=1)
        except:
            return messagebox.showerror("Error","Bad date format")

        top = tk.Toplevel(self.root); top.title("Sales Report")
        canvas = tk.Canvas(top, width=900, height=500)
        sb     = tk.Scrollbar(top, orient="vertical", command=canvas.yview)
        frm    = tk.Frame(canvas)
        frm.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0,0), window=frm, anchor="nw")
        canvas.configure(yscrollcommand=sb.set)
        canvas.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        total_sales = 0.0
        total_items = 0
        cnt = Counter()
        found = False

        for s in sales_history:
            # parse date & skip if malformed
            dt = s.get("datetime")
            try:
                t = parser.parse(dt) if dt else None
            except:
                continue
            if not t or not (sd <= t < ed):
                continue
            found = True
            subtotal = s.get("total", 0.0)
            total_sales += subtotal
            items = s.get("items", {})
            count_items = s.get("total_items", sum(items.values()))
            total_items += count_items
            cnt.update(items)
            items_str = ", ".join(f"{inventory.get(i,{}).get('name',i)} x{q}" for i,q in items.items())
            txt = (
                f"{t.strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"Items: {items_str}\n"
                f"Subtotal: {subtotal:.2f}\n"
            )
            tk.Label(frm, text=txt, justify="left").pack(anchor="w", padx=5, pady=5)

        if not found:
            tk.Label(frm, text="No sales found for this range.", fg="red")\
              .pack(pady=20)
        else:
            most = cnt.most_common(1)[0][0] if cnt else None
            name_most = inventory.get(most, {}).get("name", "N/A")
            summary = (
                f"Total Sales: {total_sales:.2f}\n"
                f"Total Items Sold: {total_items}\n"
                f"Most Sold Item: {name_most}"
            )
            tk.Label(frm, text=summary, font=("Arial",12,"bold"))\
              .pack(anchor="w", padx=5, pady=10)

    # Check inventory for items below a defined low-stock threshold
    def _low_stock_check(self):
        lows = [
            (it.get("name",""), it.get("quantity",0))
            for it in inventory.values()
            if it.get("quantity",0) < LOW_STOCK_THRESHOLD
        ]
        if lows:
            msg = "\n".join(f"{n} (Qty:{q})" for n,q in lows)
            messagebox.showwarning("Low Stock Alert", msg)

    # --- Sales page ---

    # Add selected item to the current sale (cart) after validation
    def _add_to_sale(self):
        dlg = ModalDialog(self.root, "Add to Sale", [("ID",str),("Quantity",int)])
        r = dlg.result()
        if not r: return
        i,q = r["ID"], r["Quantity"]
        if i not in inventory or q <= 0 or q > inventory[i].get("quantity",0):
            return messagebox.showerror("Error","Invalid ID or quantity")
        self.current_sale[i] = self.current_sale.get(i,0) + q
        messagebox.showinfo("Added", f"{q} x {inventory[i].get('name','')}")

    # Complete the sale transaction, generate receipt, update stock and records
    def _complete_sale(self):
        if not self.current_sale:
            return messagebox.showwarning("Empty Sale","No items in current sale")
        dlg = ModalDialog(self.root, "Complete Sale", [("Discount (%)",float),("Money Given",float)])
        r = dlg.result()
        if not r: return
        disc, money = r["Discount (%)"], r["Money Given"]
        total = sum(inventory[i].get("price",0.0)*q for i,q in self.current_sale.items())
        discount_amt = total * disc/100
        subtotal = total - discount_amt
        if money < subtotal:
            return messagebox.showerror("Error","Insufficient money")
        change = money - subtotal
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # build record
        record = {
            "datetime": now,
            "items": self.current_sale.copy(),
            "total": subtotal,
            "money_given": money,
            "change_due": change,
            "discount": disc,
            "total_items": sum(self.current_sale.values())
        }
        # update inventory
        for i,q in self.current_sale.items():
            inventory[i]["quantity"] = inventory[i].get("quantity",0) - q

        sales_history.append(record)
        save_json(DATA_FILE, inventory)
        save_json(SALES_FILE, sales_history)

        # show receipt
        lines = [
            f"{inventory.get(i,{}).get('name',i)} x{q} @ {inventory.get(i,{}).get('price',0.0):.2f}"
            f" = {inventory.get(i,{}).get('price',0.0)*q:.2f}"
            for i,q in record["items"].items()
        ]
        receipt = f"Receipt - {now}\n" + "\n".join(lines)
        receipt += (
            f"\n\nSubtotal: {total:.2f}\n"
            f"Discount: {discount_amt:.2f}\n"
            f"Total: {subtotal:.2f}\n"
            f"Paid: {money:.2f}\n"
            f"Change: {change:.2f}"
        )
        self.last_receipt = receipt
        messagebox.showinfo("Sale Complete", receipt)
        self.current_sale.clear()
        self._low_stock_check()

    # Display history of all past sales with relevant details
    def _view_sales_history(self):
        top = tk.Toplevel(self.root); top.title("Sales History")
        canvas = tk.Canvas(top, width=900, height=500)
        sb     = tk.Scrollbar(top, orient="vertical", command=canvas.yview)
        frm    = tk.Frame(canvas)
        frm.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0,0), window=frm, anchor="nw")
        canvas.configure(yscrollcommand=sb.set)
        canvas.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        for s in sales_history:
            t = s.get("datetime","")
            items = s.get("items", {})
            items_str = ", ".join(f"{inventory.get(i,{}).get('name',i)} x{q}" for i,q in items.items())
            total = s.get("total", 0.0)
            paid  = s.get("money_given", 0.0)
            ch    = s.get("change_due", 0.0)
            txt = (
                f"Date: {t}\n"
                f"Items: {items_str}\n"
                f"Total: {total:.2f} | Paid: {paid:.2f} | Change: {ch:.2f}\n"
            )
            tk.Label(frm, text=txt, justify="left").pack(anchor="w", padx=5, pady=5)


    def _print_receipt(self):
        if not self.last_receipt:
            return messagebox.showinfo("No Receipt","No recent receipt to print")
        # Option dialog
        dlg = tk.Toplevel(self.root)
        dlg.title("Print Options")
        tk.Label(dlg, text="Choose an option:").pack(pady=10)
        tk.Button(dlg, text="Save as Text", width=10,bg="#d9f0ff", fg="dark blue", activebackground="#45a049",
        font=("Arial", 12, "bold"), pady=5, command=lambda: self._save_text(dlg)).pack(pady=5)
        tk.Button(dlg, text="Print to Printer", width=10,bg="#d9f0ff", fg="dark blue", activebackground="#45a049",
        font=("Arial", 12, "bold"),  pady=5, command=lambda: self._print_direct(dlg)).pack(pady=5)

    def _save_text(self, dlg):
        # Close the dialog window
        dlg.destroy()
        path = filedialog.asksaveasfilename(defaultextension='.txt', filetypes=[('Text Files','*.txt')])
        if not path: return
        with open(path, 'w') as f:
            f.write(self.last_receipt)
        messagebox.showinfo("Saved","Receipt saved as text")

    

    def _print_direct(self, dlg):
        dlg.destroy()
        # Create a temporary file to store the receipt content
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.txt')
        tmp.write(self.last_receipt.encode('utf-8'))
        tmp.close()
        # Create a temporary file to store the receipt content
        if os.name == 'nt':
            os.startfile(tmp.name, 'print')
        else:
            messagebox.showinfo("Info","Auto-print not supported on this OS. Saved to \"%s\"" % tmp.name)


# --- Entry point ---
if __name__ == "__main__":
    login_window(lambda: InventorySystem())
f


