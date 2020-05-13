/**
 * Script for updating & querying game status
 */

// console.info("game_clock.js loaded");
var game_status;

$(document).ready(function(){
	// console.info("document ready");
	// $("#game-clock-status").text("script loaded");
	update_status(null);
  	});

function update_status(game_status){
	$.post(query_url, game_status, status_callback);
}

function status_callback(data, status){
	if (status != "success") {
		$("#game-clock-status").text(status);
	}
	else {
		$("#game-status").text("Status: " + data['status']);
		game_status = data;
	}
}


/* ensure csrf token is set on all post requests */
var csrftoken = getCookie('csrftoken');

function csrfSafeMethod(method) {
    // these HTTP methods do not require CSRF protection
    return (/^(GET|HEAD|OPTIONS|TRACE)$/.test(method));
}

$.ajaxSetup({
    beforeSend: function(xhr, settings) {
        if (!csrfSafeMethod(settings.type) && !this.crossDomain) {
            xhr.setRequestHeader("X-CSRFToken", csrftoken);
        }
    }
});

function getCookie(name) {
    var cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        var cookies = document.cookie.split(';');
        for (var i = 0; i < cookies.length; i++) {
            var cookie = cookies[i].trim();
            // Does this cookie string begin with the name we want?
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}
