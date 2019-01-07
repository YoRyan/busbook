function Tabs(tabElements) {
        this.navigation = document.createElement("ul");
        this.navigation.setAttribute("class", "tab-navigation");

        function show(idx) {
                if (idx < 0 || idx >= tabs.length)
                        throw "Invalid tab index " + idx;
                var i, tab;
                for (i = 0; i < tabs.length; i++) {
                        tab = tabs[i];
                        if (i === idx) {
                                history.replaceState(
                                        history.state, "", "#" + tab.id);
                                tab.navElement.setAttribute(
                                        "data-tab-nav-active", true);
                                tab.tabElement.setAttribute(
                                        "data-tab-content-active", true);
                        } else {
                                tab.navElement.setAttribute(
                                        "data-tab-nav-active", false);
                                tab.tabElement.setAttribute(
                                        "data-tab-content-active", false);
                        }
                }
        }
        this.show = show;

        var tabs = [];
        var i, tabElement, navItem, headers;
        for (i = 0; i < tabElements.length; i++) {
                tabElement = tabElements[i];
                navItem = document.createElement("li");
                navItem.setAttribute("data-tab-idx", i);
                navItem.addEventListener("click", function (event) {
                        const idx = parseInt(this.getAttribute("data-tab-idx"));
                        show(idx);
                });
                headers = tabElement.getElementsByClassName("tab-header");
                [...headers].forEach(function (header) {
                        [...header.childNodes].forEach(
                                child => navItem.appendChild(child));
                        header.remove();
                });
                this.navigation.appendChild(navItem);
                tabs.push({ "id": tabElement.getAttribute("id"),
                            "navElement": navItem,
                            "tabElement": tabElement });
        }

        var initIndex = tabs.findIndex(
                tab => tab.id && "#" + tab.id === location.hash);
        if (initIndex === -1)
                initIndex = 0;
        show(initIndex);
}
