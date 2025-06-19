let popup;  		//displayed popup
let popMarker;		//marker of last popup
let popLocation;	//location of last popup

let placesLayer;	// map layer for places
let oldplacesLayer; // saved placesLayer (to be replaced)

let dragStartLatLng;  // start of drag action for place

// make the osm layer
const hrefOsm = "https://www.openstreetmap.org/copyright";
const attrOsm = `© <a href='${hrefOsm}'>OpenStreetMap</a>`;
const tilesOsm = "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png";
const layerOsm = L.tileLayer(tilesOsm, { attribution: attrOsm });

const linkOsm = '<a href="http://openstreetmap.org">OpenStreetMap</a>';

// OpenCycleMap layer - requires an API key from thunderforest.com
const ocmApiKey = JSON.parse(document.getElementById('ocm-api-key').textContent);
const hrefOcm = '<a href="http://thunderforest.com/">Thunderforest</a>';
const attrOcm = '&copy; ' + linkOsm + ' Contributors & ' + hrefOcm;
const tilesOcm = 'http://{s}.tile.thunderforest.com/cycle/{z}/{x}/{y}.png?apikey='
	+ ocmApiKey;
const layerOcm = L.tileLayer(tilesOcm, { attribution: attrOcm, maxZoom: 18 });

// Google Maps / Google Satellite maps
const googleMapsUrl = 'http://{s}.google.com/vt/lyrs=m&x={x}&y={y}&z={z}';
const googleSatMapUrl = 'http://{s}.google.com/vt/lyrs=s&x={x}&y={y}&z={z}';
// terrain, traffic, biking overlays also available
const layerGoogle = L.tileLayer(googleMapsUrl, {
	maxZoom: 20, subdomains: ['mt0', 'mt1', 'mt2', 'mt3']
});
const layerGoogleSat = L.tileLayer(googleSatMapUrl, {
	maxZoom: 20, subdomains: ['mt0', 'mt1', 'mt2', 'mt3']
});

// Others copied from example using the folium package at
// https://towardsdatascience.com/build-interactive-gps-activity-maps-from-gpx-files-using-folium-cf9eebba1fe7

// national geographic
const natGeoUrl = 'https://server.arcgisonline.com/ArcGIS/rest/services/NatGeo_World_Map/MapServer/tile/{z}/{y}/{x}';
const natGeoAttr = 'Tiles &copy; Esri &mdash; National Geographic, Esri, DeLorme, NAVTEQ, UNEP-WCMC, USGS, NASA, ESA, METI, NRCAN, GEBCO, NOAA, iPC';
const layerNatGeo = L.tileLayer(natGeoUrl, natGeoAttr);

// terrain map
const terrainUrl = 'http://tile.stamen.com/terrain/{z}/{x}/{y}.jpg';
const layerTerrain = L.tileLayer(terrainUrl, attr = 'terrain-bcg');


const map = L.map("map", { layers: [layerOsm] })
	// allow user to click anywhere & show popup with lat/lon
	.on('click', onMapClick);

// map.fitWorld();


// map controls - scale, overlays
L.control.scale({ position: "bottomright" }).addTo(map);

const baseLayers = {
	OpenStreetMap: layerOsm,
	OpenCycleMap: layerOcm,
	Google: layerGoogle,
	GoogleSatellite: layerGoogleSat,
	Terrain: layerTerrain,
	NatGeographic: layerNatGeo,
};

const overlays = {
};
layerControl = L.control.layers(
	baseLayers, overlays, { position: "bottomleft" }
).addTo(map);


// place icons
const beerIcon = L.icon({
	iconUrl: '/static/icons/cup-straw-pink.svg',
	iconSize: [16, 16]
});
const coffeeIcon = L.icon({
	iconUrl: '/static/icons/cup-orange.svg',
	iconSize: [16, 16]
});
const teaIcon = L.icon({
	iconUrl: '/static/icons/teapot.svg',
	iconSize: [16, 16]
});
const placeIcon = L.icon({
	iconUrl: '/static/icons/geo-green.svg',
	iconSize: [16, 16]
});
const cameraIcon = L.icon({
	iconUrl: '/static/icons/camera-yellow.svg',
	iconSize: [16, 16]
});
const bullseyeIcon = L.icon({ // unused
	iconUrl: '/static/icons/bullseye-blue.svg',
	iconSize: [16, 16]
});


// add tracks & markers sent with map

const track = L.geoJSON(
	JSON.parse(document.getElementById("tracks").textContent),
)
	.bindPopup((layer) => layer.feature.properties.name)
	.addTo(map);

//const feature = L.geoJSON(
//  JSON.parse(document.getElementById("markers").textContent),
//)
//  .bindPopup((layer) => layer.feature.properties.name)
//  .addTo(map);

makePlaceLayer(JSON.parse(document.getElementById("markers").textContent),)


function makePlaceLayer(data) {
	var newPlacesLayer = L.geoJSON(data, {
		pointToLayer: getPlaceMarker,
		onEachFeature: onPlaceShow
	});
	// showSidebarSection(true, 'place');
	placesLayer = replaceMapOverlay(placesLayer, newPlacesLayer, "Places");
	placesBounds = placesLayer.getBounds();
	setMapBounds();
}

function setMapBounds() {
	// resize the map to fit placesBounds and tracksBounds
	map.fitBounds(placesLayer.getBounds().extend(track.getBounds()));
	return;
	var combinedBounds;
	if (placesBounds) {
		if (tracksBounds) {
			// combine both
			var combinedBounds = L.latLngBounds(tracksBounds.getNorthEast(),
				tracksBounds.getSouthWest());
			combinedBounds.extend(tracksBounds);
		}
		else {
			combinedBounds = placesBounds;
		}
	}
	else if (tracksBounds) {
		combinedBounds = tracksBounds
	}
	else {  // neither tracksBounds or placesBounds are specified
		return;  // do nothing
	}
	map.fitBounds(combinedBounds);
}


// create popup when user clicks on map
// these buttons shown when no tracks are visible on the map
const nearbyButtons1Html = `<p>
<button onClick="nearbyTracks()" class="btn">Nearby Tracks</button>
<button class="btn" onClick="nearbyPlaces()">Nearby Places</button>
</p>`;

// these buttons shown if tracks are already visible on the map
const nearbyButtons2Html = `<p>
<div class="btn-group">
<button onClick="nearbyTracks()" class="btn">Nearby Tracks</button>
  <button type="button" class="btn dropdown-toggle dropdown-toggle-split"
	data-bs-toggle="dropdown" aria-expanded="false">
    <span class="visually-hidden">Toggle Dropdown</span>
  </button>
  <ul class="dropdown-menu">
    <li><button class="btn dropdown-item" onClick="nearbyTracks('add')">
	  Add to tracks already displayed</button></li>
    <li><button class="btn dropdown-item" onClick="nearbyTracks('reduce')">
	  Search only tracks already displayed</button></li>
  </ul>
</div>
<button class="btn" onClick="nearbyPlaces()">Nearby Places</button>
</p>`;

function onMapClick(event) {
	popLocation = event.latlng;
	var buttonsHtml = map.hasLayer(tracks) ? nearbyButtons2Html : nearbyButtons1Html;
	L.popup()
		.setLatLng(popLocation)
		.setContent(
			'<p>You clicked at ' + popLocation.toString() + `</p>
			<button type="button" class="btn" onClick="createPlace()">
			New Place</button>` +
			buttonsHtml)
		.openOn(map);
	// TODO: if tracks layer is not shown, don't show additional track options      
}

function replaceMapOverlay(oldOverlay, newOverlay, overlayName) {
	if (oldOverlay) {
		map.removeLayer(oldOverlay);
		layerControl.removeLayer(oldOverlay);
	}
	map.addLayer(newOverlay);
	layerControl.addOverlay(newOverlay, overlayName);
	return newOverlay;
}


// error handling
function requestFailMsg(errMsg) {
	var msg = errMsg;
	if (errMsg.status) {
		msg = "Status code " + errMsg.status + ": " + errMsg.statusText;
	}
	msg = "Server request " + requestUrl + " returned " + msg;
	console.error(msg + ': ' + errMsg)
	window.alert(msg + ': ' + errMsg);
	// log_error(msg, errMsg);
}

function ajaxFail(jqXHR, textStatus, errorThrown) {
	// translate to a requestFailMsg call
	requestFailMsg({ "status": textStatus, "statusText": errorThrown });
}
/*
// ------ place handling ------
*/
// handle 'new place' 

function createPlace() {
	requestUrl = "/routes/place";
	$.get(requestUrl, null, showPlaceForm, 'html')
		.fail(requestFailMsg);
}

function showPlaceForm(data) {
	popup = L.popup()
		.setLatLng(popLocation)
		.setContent(data)
		.openOn(map);
}

function onPlaceFormSubmit(event) {
	// submit the place form using html/post
	// expects a json response if all ok
	// if form errors, an html response is received, which triggers error
	// handling
	event.preventDefault();

	// fill in hidden values in form for position
	document.getElementById("place-lat").value = popLocation.lat;
	document.getElementById("place-lon").value = popLocation.lng;
	let formData = new FormData(event.target);
	let pk = formData.get("pk")
	let requestUrl = "/routes/place/" + (pk ? pk: "")
	
	$.ajax({
		url: requestUrl,
		method: 'POST',
		data: formData,
		processData: false,
		contentType: false,
		dataType: "json",  // if not json, error will be called
		success: formData["pk"] ? placeUpdateOK : placeInsertOK,
		error: function(jqXHR, textStatus, errorThrown) {
			alert('Your request was not sent successfully.');
			console.error(errorThrown);
		}
	});
}

function placeUpdateOK(data) {
	/*  update the existing marker's name & close the popup */
	popup.remove();  // popup isn't attached to a marker, just to the map
	popMarker.options.placeName= data["name"];
	popMarker.options.placeID = data["pk"]
}

function placeInsertOK(data) {
	/* add a new marker for the new place 
	   data = name, pk, type */
	const fakeFeature = { properties: data };
	let placeMarker = getPlaceMarker(fakeFeature, popLocation)
		.on("click", onPlaceClick);
	//console.info("placeInsertOK(data=", data, "): feature=", fakeFeature,
	//			 ", latlon=", popLocation, " -> marker=", placeMarker);
	oldPlacesLayer = placesLayer;
	if (!placesLayer) {
		placesLayer = L.layerGroup([]);
	}
	placesLayer.addLayer(placeMarker);
	replaceMapOverlay(oldPlacesLayer, placesLayer, "Places");
	popup.remove();
}

function getPlaceMarker(feature, latlng) {
	/* return a marker depending on the type of the feature */

	var sel_icon, marker;
	switch (feature.properties.type) {
		case 'P':
			sel_icon = beerIcon;
			break;
		case '11':
			sel_icon = coffeeIcon;
			break;
		case 'T':
			sel_icon = teaIcon;
			break;
		case 'L':
			sel_icon = placeIcon;
			break;
		case 'C':
			sel_icon = cameraIcon;
			break;
		default:
			sel_icon = placeIcon;
	}
	marker = L.marker(latlng, {
		icon: sel_icon,
		draggable: true,
		placeID: feature.properties.pk,
		placeName: feature.properties.name
	})
		.on('dragstart', placeDragStart)
		.on('dragend', placeDragEnd);
	return marker;
}

function placeDragStart(event) {
	dragStartLatLng = event.target.getLatLng();
}

function placeDragEnd(event) {
	popMarker = event.target;
	var newPos = popMarker.getLatLng();
	requestUrl = "/routes/place/" + popMarker.options.placeID + "/move"
	$.ajax({
		url: requestUrl,
		method: "GET",
		dataType: "html",
		success: function(content){
			// open a popup to confirm the move
			popup = L.popup().setContent(content);
				popMarker.bindPopup(popup)
					.openPopup();
		},
		error: function() {
			onPlaceMoveUndo();
			requestFailMsg();
		}
	});
}

function onPlaceMoveConfirm(event) {
	event.preventDefault();
	newPos = popMarker.getLatLng();
	document.getElementById("place-move-lat").value = newPos.lat;
	document.getElementById("place-move-lon").value = newPos.lng;
	var formData = new FormData(event.target);
	var pk = formData.get("pk")
	requestUrl = "/routes/place/" + pk + "/move"
		
	$.ajax({
		url: requestUrl,
		method: 'POST',
		data: formData,
		processData: false,
		contentType: false,
		success: null,
		error: requestFailMsg
	});
	if (popup) {popup.remove();}
}

function onPlaceMoveUndo() {
	// move back to original place (also called from place_move form)
	console.info("move cancelled.");
	if (popup) {popup.remove();}
	popMarker.setLatLng(dragStartLatLng);
}

function onPlaceShow(feature, layer) {
	layer.on({
		click: onPlaceClick,
		mouseover: onPlaceMouseOver,
		mouseout: onPlaceMouseLeave
	});
	// addToPlaceSidebar(feature, layer);
}

const placePopupContent = `<p>{{name}}</p>
<button class="btn btn-light" type="button"
onClick="placeDetails()">Details</button>
<button class="btn btn-outline-danger" type="button"
onClick="placeDelete({{id}})">Delete</button>`

function onPlaceClick(event) {
	// open a popup menu about the place
	popMarker = event.target;
	popLocation = popMarker.getLatLng();  // for showPlaceForm
	let content = placePopupContent
		.replace('\{\{name\}\}', popMarker.options.placeName)
		.replace('\{\{id\}\}', popMarker.options.placeID);
	popup = popMarker.getPopup();
	if (popup) {
		popMarker.unbindPopup();  // it can't be reopened (?)
	}
	popup = L.popup().setContent(content);
	popMarker.bindPopup(popup)
		.openPopup();
}

function placeDetails() {
	// console.info("popMarker=", popMarker);
	requestUrl = "/routes/place/" + popMarker.options.placeID.toString();
	$.get(requestUrl, null, showPlaceForm, 'html')
		.fail(requestFailMsg);
}

function placeDelete(pk) {
	// request the deletion form (inc csrf token) from the server
	if (pk != popMarker.options.placeID) {
		alert("placeDelete: place id doesn't match:" + pk + " vs. "
			  + popMarker.options.placeID);
	}
	$.get("/routes/place/" + pk.toString() + "/delete", "",
		  placeConfirmDelete, "html", {error: requestFailMsg})
}

function placeConfirmDelete(form) {
	// shows an html form to confirm deletion of a place
	let popup = popMarker.getPopup();
	popup.setContent(form);
}

function onPlaceDoDelete(event) {
	// after confirmation, do the delete (with csrf token)
	//if (confirm("delete " + popMarker.options.placeName + " (pk=" + pk + ")?")
	event.preventDefault();
	var formData = new FormData(event.target);
	var pk = formData.get("pk")
	requestUrl = "/routes/place/" + pk.toString() + "/delete"
	// alert("onPlaceDoDelete: requestUrl=(" + requestUrl);
	$.ajax({
		url: requestUrl,
		method: "POST",
		data: formData,
		processData: false,
	    contentType: false,
		dataType: "json",
		success: function(data) {
			// popMarker.remove();  // this also removes the popup
			placesLayer.removeLayer(popMarker);
		},
		error: requestFailMsg
	}
	);
}

function onPlaceMouseOver(ev) {
	layerChangeState(ev.target, 'place', true, null);
	const placeID = ev.target.feature.properties.pk;
	$("#place-sidebar-item-" + placeID).addClass("highlight");
}

function onPlaceMouseLeave(ev) {
	const placeID = ev.target.feature.properties.pk;
	$("#place-sidebar-item-" + placeID).removeClass("highlight");
	layerChangeState(ev.target, 'place', false, null);
}

// ----- control highlighting of places & tracks ------

/* layer highlighting has 4 states, like 4 corners of a square:
   No highlight:   mouse enter -> hovering; select -> selected
   Selected and hovering: mouse leave -> selected; deselect -> hovering
   Selected:  mouse enter -> sel & hovering; deselect -> none
   Hovering:  mouse leave -> none; select -> sel & hovering

   Visually, hovering has precedence, so hover + select looks like hover
*/

function layerChangeState(layer, itemType, hovering, selected) {
	if (!layer.feature) {
		console.error("layerChangeState(", layer, ")");
		throw Error("layerChangeState invalid without layer.feature");
	}
	if (!layer.feature.properties.state) {
		layer.feature.properties.state = {};
	}
	if (hovering !== null) {
		layer.feature.properties.state.hovering = hovering;
	}
	if (selected !== null) {
		layer.feature.properties.state.selected = selected;
	}
	let style = getLayerStyle(itemType, layer.feature.properties.state);
	// console.info("layerStateChange(..",hovering, selected,"): style=", style);
	layerUpdateHilight(layer, itemType, style);
}

const trackHoverStyle = {
	color: 'Indigo',
	opacity: 1.0
};

const trackSelectedStyle = {
	color: 'DeepPink',
	opacity: 1.0
};

const placeHoverStyle = {
	radius: 10,
	stroke: false,
	fill: true,
	fillColor: '#ffff00',  // yellow
	fillOpacity: 0.5,
	interactive: false,   // don't emit mouse events, pass to map
};

const placeSelectedStyle = {
	radius: 10,
	stroke: true,
	weight: 2,  // px
	color: 'DeepPink',   // '#cc00cc',  // grey
	opacity: 1.0,
	fill: false,
	interactive: false,   // don't emit mouse events, pass to map
};

function getLayerStyle(itemType, state) {
	/* return the hilight style, or null if not highlighted */
	// console.info("getLayerStyle(", itemType, state, ")");
	if (state.hovering) {
		return itemType == 'track' ? trackHoverStyle : placeHoverStyle;
	} else if (state.selected) {
		return itemType == 'track' ? trackSelectedStyle : placeSelectedStyle;
	} else {
		return null;
	}
}

function layerUpdateHilight(layer, itemType, style) {
	if (itemType == 'track') {
		if (style) {
			layer.setStyle(style);
			layer.bringToFront();
		} else {
			tracksGeoLayer.resetStyle(layer);
		}
	} else if (itemType == 'place') {
		if (layer.feature.properties.prevHilight) {
			layer.feature.properties.prevHilight.removeFrom(placesLayer);
		}
		if (style) {
			let hilight = L.circleMarker(layer.getLatLng(), style);
			hilight.addTo(placesLayer);
			layer.feature.properties.prevHilight = hilight;
		} else {
			layer.feature.properties.prevHilight = null;
		}
	}
}


// ---- utilities ----

function formArrayToJSON(arrayData) {
	// convert an array of {name: value: } dicts to a single dict {name: value}
	result = {};

	arrayData.forEach(function(fieldData) {
		result[fieldData['name']] = fieldData['value'];
	});

	/* $.map(arrayData, function(fieldData) {
		result[fieldData['name']] = fieldData['value'];
	}); */

	return result;
}
