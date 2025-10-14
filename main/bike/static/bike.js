// javascript for bike website

function change_link_visibility(id) {
	/* switch visibility for row#id:
	find tr#link_id>td.link-link, add class hidden
	find tr#link_id>td.link-form, remove class hidden */
	// row = $('tr#link_' + id).get();
	link = $('tr#link_' + id).find('td.link-link').addClass('hidden');
	form = $('tr#link_' + id).find('td.link-form').removeClass('hidden');
}

function mark_link_deleted(id) {
	/* toggle: mark form deleted and set strikethrough */

	// <input> for deleted has id id_links-0-DELETE vs passed id=id_links-0-id
	delete_id = id.slice(0, -3) + "-DELETE";
	deleted_old = $('#' + delete_id).prop("checked");
	deleted = !deleted_old;
	console.info("link", id, "deleted_old=", deleted_old, "deleted =", deleted);
	$('#' + delete_id).prop("checked", deleted);
	
	// find the link itself and set strikethrough
	link = $('tr#link_' + id).find('a')[0];
	link.style.textDecoration = deleted ? "line-through": "underline";
	console.info("results: input.checked=", $('#' + delete_id).prop("checked"),
		"link.style.textDecoration=", link.style.textDecoration);
}

function onLoadMoreMaintHistory(params){
	// get the requested page of the maint history and load it into the table
	requestUrl = "/bike/maint/history?" + $.param(params)
	$.get(requestUrl, null,
		function(html){$("#maintenance-history").html(html);},
		"html"
	).fail(requestFailMsg);
}


// error handling
function requestFailMsg(jqXHR, textStatus, errorThrown) {
	console.debug("Request failed:",
		{jqXHR: jqXHR, textStatus: textStatus, errorThrown: errorThrown,
		 requestURL: requestUrl
		});
	if (jqXHR.responseText.startsWith("<!DOCTYPE html>")) {
		// it's an unexpected html failure message, could be django debug info
		document.open()
		document.write(jqXHR.responseText);
		document.close()
		return
	}
	let msg = jqXHR;
	if (jqXHR.status) {
		msg = "Status code " + jqXHR.status + ": " + (jqXHR.responseText ? jqXHR.responseText: jqXHR.statusText);
	}
	log_error(msg);
}

function log_error(msg) {
	console.error(msg, "; from server request=", requestUrl);
	console.info("trackSearchHistory=", trackSearchHistory);
	displayMessage("Error: " + msg, "text-error");
}

function displayMessage(message, msgClass) {
	/* display a message in the message area.  msg_class, if provided,
	is a bootstrap class such as text-info/warning/error/success */
	let html = "<li";
	if (msgClass) {
		html += ' class="' + msgClass + '"';
	}
	html += ">" + message + "</li>";
	// console.info("displayMessage(", message, ") -> html: ", html);
	$("#messages").html(html);
	showMessages();
}

function showMessages() {
	/* show pre-set messages for 3.5 seconds
	If the header is not shown, we have to show it or messages are invisible
	*/
	let element = document.getElementById("messages");
	//let baseHeaderElement = document.getElementById("base-header")
	//let navIsHidden = baseHeaderElement.classList.contains("d-none");
	//if (navIsHidden) {
	//	baseHeaderElement.classList.remove("d-none");
	//}
	element.classList.remove("d-none") ;

	setTimeout(function() {
		element.classList.add("d-none");
	//	if (navIsHidden) {
	//		baseHeaderElement.classList.add("d-none");
	//	}
	}, 3500);
}

const preferencesFormTabs = {
	"nav-units-tab": 1,
	"nav-maintenance-tab": 2,
	"nav-search-tab": 3
}

function onPreferencesFormSubmit(event, action) {
	/* calculate and add the prefs_page param to the form's url.
	The form is submitted using default browser handling for a submit event */
	event.preventDefault();
	let prefs_page = undefined;
	console.info("event.target=", event.target, "action=", action);
	let form = document.getElementById("preferences-form");
	Object.keys(preferencesFormTabs).forEach(
		function(id){
			if (document.getElementById(id).classList.contains("active")) {
				prefs_page = preferencesFormTabs[id];
				let url = form.action;
				let newUrl = setQSValue(url, "prefs_page=", prefs_page);
				newUrl = setQSValue(newUrl, "action=", action);
				form.action = newUrl;
				console.info("new url =", newUrl, "new action=", form.action);
				if (newUrl != form.action) {
					alert("failed to set Preferences form.action - see console");
				}
				form.submit();
				return;
		}
	});
	if (prefs_page === undefined) {
		console.error("No active Preferences form tab found", event);
		displayMessage("Submit failed", "text-error");
		event.preventDefault();
	}
}

function setQSValue(url, key, value)
/* set a query string value within a url.  The key should contain an = sign */ 
{
    let query_string = url.split('?');
	let string_values = query_string.length == 1 ? [] : query_string[1].split('&');
	let req_value = undefined;
    for(i=0;  i < string_values.length; i++)
    {
        if( string_values[i].match(key)) {
            req_value = string_values[i].split('=');
			string_values[i] = key + value
		}    
    }
	if (req_value === undefined) {
		string_values.push(key+value);
	}
	// recreate url params
    query_string[1] = string_values.join('&')
	return query_string.join('?')
}