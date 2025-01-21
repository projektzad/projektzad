from flask import Flask, jsonify
from ldap3 import Server, Connection, ALL, SUBTREE

app = Flask(__name__)

@app.route('/attributes', methods=['GET'])
def get_all_attributes(conn):
    try:
        # Połączenie z serwerem LDAP
        # Przechodzimy do kontenera schematu
        conn.search(
            search_base='CN=Schema,CN=Configuration,DC=yourdomain,DC=com',
            search_filter='(objectClass=attributeSchema)',
            search_scope=SUBTREE,
            attributes=['lDAPDisplayName']
        )

        # Pobranie listy atrybutów
        attributes = [entry['attributes']['lDAPDisplayName'][0] for entry in conn.entries]
        return jsonify({"attributes": attributes})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
