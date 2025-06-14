let popup;  		//displayed popup
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
const hrefOcm = '<a href="http://thunderforest.com/">Thunderforest</a>';
const attrOcm = '&copy; '+linkOsm+' Contributors & ' + hrefOcm;
const tilesOcm = 'http://{s}.tile.thunderforest.com/cycle/{z}/{x}/{y}.png?apikey='
				+ ocm_api_key;
const layerOcm = L.tileLayer(tilesOcm, {attribution: attrOcm, maxZoom: 18});

// Google Maps / Google Satellite maps
const googleMapsUrl= 'http://{s}.google.com/vt/lyrs=m&x={x}&y={y}&z={z}';
const googleSatMapUrl = 'http://{s}.google.com/vt/lyrs=s&x={x}&y={y}&z={z}';
// terrain, traffic, biking overlays also available
const layerGoogle = L.tileLayer(googleMapsUrl,  {
	maxZoom: 20, subdomains: ['mt0', 'mt1', 'mt2', 'mt3']});
const layerGoogleSat = L.tileLayer(googleSatMapUrl, {
	maxZoom: 20, subdomains: ['mt0', 'mt1', 'mt2', 'mt3']});

// Others copied from example using the folium package at
// https://towardsdatascience.com/build-interactive-gps-activity-maps-from-gpx-files-using-folium-cf9eebba1fe7

// national geographic
const natGeoUrl = 'https://server.arcgisonline.com/ArcGIS/rest/services/NatGeo_World_Map/MapServer/tile/{z}/{y}/{x}';
const natGeoAttr='Tiles &copy; Esri &mdash; National Geographic, Esri, DeLorme, NAVTEQ, UNEP-WCMC, USGS, NASA, ESA, METI, NRCAN, GEBCO, NOAA, iPC';
const layerNatGeo = L.tileLayer(natGeoUrl, natGeoAttr);

// terrain map
const terrainUrl = 'http://tile.stamen.com/terrain/{z}/{x}/{y}.jpg';
const layerTerrain = L.tileLayer(terrainUrl, attr='terrain-bcg');


const map = L.map("map", { layers: [layerOsm] });

// map.fitWorld();


// map controls - scale, overlays
L.control.scale({position: "bottomright"}).addTo(map);

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
	baseLayers, overlays, {position: "bottomleft"}
).addTo(map);


// allow user to click anywhere & show popup with lat/lon
	map.on('click', onMapClick);
		
		
// add tracks & markers sent with map
const feature = L.geoJSON(
  JSON.parse(document.getElementById("markers").textContent),
)
  .bindPopup((layer) => layer.feature.properties.name)
  .addTo(map);

const track = L.geoJSON(
	JSON.parse(document.getElementById("tracks").textContent),
)
  .bindPopup((layer) => layer.feature.properties.name)
  .addTo(map);

map.fitBounds(feature.getBounds().extend(track.getBounds()));


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
	popLocation= event.latlng;
	var buttonsHtml = map.hasLayer(tracks)? nearbyButtons2Html:nearbyButtons1Html; 
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

function replaceMapOverlay(oldOverlay, newOverlay, overlayName){
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
	requestFailMsg({"status": textStatus, "statusText": errorThrown});
}

// ------ place handling ------
// icons for place display
const beerIcon = L.icon({
	iconUrl: '/routes/static/icons/cup-straw-pink.svg',
	iconSize: [16, 16]});
const coffeeIcon = L.icon({
	iconUrl: '/routes/static/icons/cup-orange.svg',
	iconSize: [16, 16]});
const teaIcon = L.icon({
	iconUrl: '/routes/static/icons/teapot.svg',
	iconSize: [16, 16]});
const placeIcon = L.icon({
	iconUrl: '/routes/static/icons/geo-green.svg',
	iconSize: [16, 16]});
const cameraIcon = L.icon({
	iconUrl: '/routes/static/icons/camera-yellow.svg',
	iconSize: [16,16]});
const bullseyeIcon = L.icon({ // unused
	iconUrl: '/routes/static/icons/bullseye-blue.svg',
	iconSize:[16,16]});


// handle 'new place' 

function createPlace() {
	requestUrl = "/routes/place?lat=" + popLocation.lat+'&lon='+popLocation.lng;
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
	event.preventDefault();
	            
    var form = document.getElementById('placeForm');
    var formData = new FormData(form);
 	//console.info("onPlaceFormSubmit: formData=", formData.toString())
	
    $.ajax({
        url: "/routes/place/",
        method: 'POST',
        data: formData,
        processData: false,
        contentType: false,
        success: formData["id"] ? placeUpdateOK: placeInsertOK,                 
        error: function (xhr, status, error) {                       
            alert('Your reqiest was not sent successfully.');
            console.error(error);
        }
    });
}
	
function OLDonPlaceFormSubmit(event) {
	event.preventDefault();
	let data = $("#placeForm").serializeArray();
	let jsonData = formArrayToJSON(data);
	let jsonStringData = JSON.stringify( jsonData );
	requestUrl = "/routes/place/";
	if (jsonData['id']) {
		requestUrl += jsonData['id'];
	}
	
	$.ajax({
		method: "POST",
		url: requestUrl,
		data: jsonStringData,
		contentType: "application/json; charset=utf-8",
	  	dataType: "json",
			headers: {"X-CSRFToken": jsonData["csrfmiddlewaretoken"],
				'X-Requested-With': 'XMLHttpRequest',  // Important for Django to recognize the AJAX request
		                },
		success: jsonData["id"] ? placeUpdateOK: placeInsertOK,
		error: ajaxFail
	});
	return false;  // prevent propagation
}

function placeUpdateOK(data) {
	/*  update the existing marker's name & close the popup */
	responseType = data.getResponseHeader("Content-Type")
	
	console.info("placeUpdateOK(", data, "), responseType=", responseType);
	popup.remove();  // popup isn't attached to a marker, just to the map
	popMarker.options.placeName = data["name"];
	popMarker.options.placeID = data["id"]
}

function placeInsertOK(data) {
	/* add a new marker for the new place 
	   data = name, id, type */
	const fakeFeature = {properties: data};
	const placeLatLon = L.latLng(data.lat, data.lon);
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

function getPlaceMarker(feature, latlng){
	/* return a marker depending on the type of the feature */

	var sel_icon, marker;
	switch(feature.properties.type.toUpperCase()){
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
		placeID: feature.properties.id,
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
	var marker = event.target;
	var pos = marker.getLatLng();
	var name = marker.options.placeName;
	if (confirm("Move " + name + " to " + pos + "?")) {
		updatePlaceLocation({
			id: marker.options.placeID,
			lat: pos.lat,
			lon: pos.lng});
	} else {
		// move back to original place
		console.info("cancelled.  Event info=", event)
		marker.setLatLng(dragStartLatLng);
	};
}

function updatePlaceLocation(data) {
	alert("Not yet implemented: updatePlaceLocation" + data.toString());
}

function onPlaceClick(data) {
	console.info("Not yet implemented: onPlaceClick", data.toString());
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
