function IRCViewer(messageDiv, updateTime) {
    this.messageDiv = messageDiv;
    this.updateTime = updateTime;
}

IRCViewer.prototype = {

    formatTime: function(timestamp) {
        var time = new Date(timestamp * 1000);
        var zeroPad = function(str, size) {
            while (str.length < size) {
                str = "0" + str;
            }
            return str;
        };
        var hours = zeroPad(String(time.getHours()), 2);
        var minutes = zeroPad(String(time.getMinutes()), 2);
        return hours + ":" + minutes;
    },

    addMessage: function(message) {
        var timeStr = this.formatTime(message['timestamp']);
        var html = '<div class="message">';
        html += '<span class="time">[' + timeStr + ']</span> ';
        html += '<span class="user">' + message['user'] + ':</span> ';
        html += message['message'] + '</div>';

        this.messageDiv.append(html);
    },

    userJoined: function(message) {
        var timeStr = this.formatTime(message['timestamp']);
        var html = '<div class="message">';
        html += '<span class="time">[' + timeStr + ']</span> ';
        html += '<span class="user">' + message['user'] + ' joined</span> ';
        html += '</div>';

        this.messageDiv.append(html);
    },

    userLeft: function(message) {
        var timeStr = this.formatTime(message['timestamp']);
        var html = '<div class="message">';
        html += '<span class="time">[' + timeStr + ']</span> ';
        html += '<span class="user">' + message['user'] + ' left</span> ';
        html += '</div>';

        this.messageDiv.append(html);
    },

    userQuit: function(message) {
        var timeStr = this.formatTime(message['timestamp']);
        var html = '<div class="message">';
        html += '<span class="time">[' + timeStr + ']</span> ';
        html += '<span class="user">' + message['user'] + ' quit</span> ';
        html += '</div>';

        this.messageDiv.append(html);
    },

    handleAction: function(action) {
        switch (action['command']) {
        case 'privmsg':
            this.addMessage(action);
            break;
        case 'userjoined':
            this.userJoined(action);
            break;
        case 'userleft':
            this.userLeft(action);
            break;
        case 'userquit':
            this.userQuit(action);
            break;
        } 
        this.messageDiv[0].scrollTop = this.messageDiv[0].scrollHeight;
    },

    doUpdate: function() {
        var self = this;
        $.ajax({
            url: '/update.js', 
            dataType: 'json',
            success: function(action) {
                if (action && action['command']) {
                    self.handleAction(action)
                }
                self.doLoop();
            },
            error: function(xhr, textStatus, error) {
                self.doLoop();
            }
        });
    },

    run: function() {
        var self = this;
        $.getJSON('/history.js', function(history) {
            for (var i in history) {
                var action = history[i];
                self.handleAction(action);
            }
            self.doLoop();
        });
    },

    doLoop: function() {
        var self = this;
        setTimeout(function() {
            self.doUpdate();
        }, this.updateTime);
    }

};

window.IRCViewer = IRCViewer;
