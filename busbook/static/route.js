/* Read route colors. */
BodyStyle = getComputedStyle(document.body)
RouteColor = BodyStyle.getPropertyValue("--route-color");
RouteTextColor = BodyStyle.getPropertyValue("--route-text-color");

/* Initialize tabbed navigation. */
RouteTabs = new Tabs(document.getElementsByTagName("section"));
Header = document.getElementsByTagName("header")[0];
Header.appendChild(RouteTabs.navigation);

/* Create map and base layers. */
const OsmLayer = new L.TileLayer(
        "https://{s}.tile.openstreetmap.se/hydda/full/{z}/{x}/{y}.png",
        { attribution: 'Map &copy; <a href="https://openstreetmap.org">'
                        + 'OpenStreetMap</a>' }),
      EsriLayer = new L.tileLayer(
        "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/"
        + "MapServer/tile/{z}/{y}/{x}",
        { attribution: "Tiles &copy; Esri &mdash; Source: Esri, i-cubed, USDA, "
                       + "USGS, AEX, GeoEye, Getmapping, Aerogrid, IGN, IGP, "
                       + "UPR-EGP, and the GIS User Community" });
RouteMap = L.map("route-map", { fullscreenControl: { pseudoFullscreen: true } })
        .addLayer(OsmLayer)
L.control.layers({ "OpenStreetMap": OsmLayer,
                   "Satellite (Esri)": EsriLayer })
        .addTo(RouteMap);
RouteBounds = new L.LatLngBounds(Stops.map(stop => [stop.stop_lat, stop.stop_lon]));
RouteMap.fitBounds(RouteBounds);

/* Recompute map size after CSS transitions. */
document.getElementById("route-map")
        .addEventListener("transitionend",
                          function (event) { RouteMap.invalidateSize(); });

/* Add route lines and stops. */
function MakeTooltip(stop, layer) {
        layer.bindTooltip(stop.stop_name);
        return layer;
}
L.polyline(Shapes, { color: RouteColor })
        .addTo(RouteMap);
Stops.forEach(function (stop) {
        var marker;
        if (Timepoints.find(timepoint => timepoint.stop_id === stop.stop_id)
            === undefined) {
                marker = L.circleMarker([stop.stop_lat, stop.stop_lon],
                                        { radius: 8,
                                          stroke: true,
                                          color: RouteTextColor,
                                          fillColor: RouteColor,
                                          fillOpacity: 1.0 })
                        .addTo(RouteMap);
                MakeTooltip(stop, marker);
        }
});
Timepoints.forEach(function (stop) {
        var marker = L.marker([stop.stop_lat, stop.stop_lon], title=stop.stop_name)
                .addTo(RouteMap);
        MakeTooltip(stop, marker);
});
