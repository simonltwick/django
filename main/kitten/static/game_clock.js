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

// when game-control button pressed, send the text to the server
$("#game-control").click(function(){
	update_status($("#game-control").text());
});

function update_status(game_status){
	// console.info("update_status(", game_status, ")");
	$.post(query_url, {'status': game_status}, status_callback);
}

function status_callback(data, status){
	if (status != "success") {
		$("#game-clock-status").text(status);
	}
	else {
		$("#game-status").text("Status: " + data['status']);
		game_status = data['status'];
		update_game_control_button();
	}
}


var game_state_action_map = [
	['Between Days', 'Play'],
	['Between Stages', 'Play'],
	['Paused', 'Play'],
	['Running', 'Pause'],
	['Play Requested', 'Play', 'Cancel'],
	['Pause Requested', 'Pause', 'Cancel']
]

function update_game_control_button(){
	/* set the game control button to play/cancel/pause depending on status*/
	/* map game_status to button action as follows
	 *  Game status: ->  button action (see game_state_action_map)
	 *    BETWEEN_DAYS       Play
     *    BETWEEN_STAGES     Play
     *    PAUSED             Play
     *    RUNNING            Pause
     *    PLAY_REQUESTED     Cancel [Play] if you are the requestor, else Play
     *    PAUSE_REQUESTED    Cancel [Pause]  ------"-----, else Pause
	 */
	button_status = null;
	for (option of game_state_action_map){
		if (game_status == option[0]) {
			button_status = option[1];  // or option 2 if .. pending due to me
			break;
		}
	}
	// console.info("button_status =", button_status);
	if (button_status == null) {
		$("#game_control").prop("disabled", true);
		$("#game-clock-status").text("Unrecognised game_status");
	}
	else {
		$("#game-control").prop("disabled", false);
		$("#game-control").text(button_status);
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
