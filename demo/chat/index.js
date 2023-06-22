
const env = {}

env.websocket_protocol = (window.location.protocol==='http:')?'ws:':'wss:'
env.websocket_base_url = window.location.origin.replace(window.location.protocol, env.websocket_protocol)

let sock = null
let keepalive_timer = null
let username = "unknown user"

function handleMessageReceived(obj) {
        var divn = document.createElement("div");
        var txtn = document.createTextNode(obj.username);
        divn.appendChild(txtn)

        if (obj.username == username) {
            cls_name = 'local_user_name'
            cls_msg = 'local_user_message'
        } else if (obj.username == "system") {
            cls_name = 'system_user_name'
            cls_msg = 'system_user_message'
        } else {
            cls_name = 'remote_user_name'
            cls_msg = 'remote_user_message'
        }

        divn.classList.add(cls_name);

        var divm = document.createElement("div");
        var txtm = document.createTextNode(obj.message);
        divm.appendChild(txtm)
        divm.classList.add(cls_msg);

        var div = document.createElement("div");
        div.appendChild(divn)
        div.appendChild(divm)

        var box = document.getElementById("vbox");
        box.appendChild(div)

        window.scrollTo(0, document.body.scrollHeight);
}
function connect() {
    sock = new WebSocket(env.websocket_base_url + "/ws")

    sock.onopen = function(e) {
        console.log("opened")

        keepalive_timer = setInterval(()=>{
            payload = JSON.stringify({'type': 'keepalive'})
            sock.send(payload)
        }, 1000)




    }

    sock.onmessage = function(e) {

        console.log(e.data)
        obj = JSON.parse(e.data)
        if (obj.type == "message") {
            handleMessageReceived(obj)
        } else if (obj.type == "setusername") {
            username = obj.username

            handleMessageReceived({
                "type": "message",
                "username": "system",
                "message": username + " connected to server",
            })

        } else {
            console.log(obj.type)
        }
    }

    sock.onclose = function(e) {
        if (e.wasClean) {
            console.log(e.code, e.reason)
        } else {
            handleMessageReceived({
                "type": "message",
                "username": "system",
                "message": "connection lost",
            })
        }
    }

    sock.onerror = function(e) {
        console.error(e)
        console.error(e.message)
    }

    console.log("sock created")



}
function main() {

    connect()

    const box = document.getElementById("chatbox");
    box.addEventListener("keyup", function(event) {
        if (event.key === "Enter") {
            payload = JSON.stringify({
                'type': 'message',
                'message': box.value,
                'username': username
            })
            sock.send(payload)
            box.value = ""
        }
    });


}