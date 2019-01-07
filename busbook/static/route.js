RouteTabs = new Tabs(document.getElementsByTagName("section"));
NavSection = document.createElement("section");
NavSection.appendChild(RouteTabs.navigation);
Main = document.getElementsByTagName("main")[0];
Main.insertBefore(NavSection, Main.firstChild);
