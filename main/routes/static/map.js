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
		baseLayers, overlays, {position: "bottomleft"}).addTo(map);
		
		
// add tracks & markers
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

