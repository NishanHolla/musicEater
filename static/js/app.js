const songsContainer = document.getElementById("songs");

const player = document.getElementById("audioPlayer");

const playerTitle = document.getElementById("playerTitle");

const playerUploader = document.getElementById("playerUploader");

const playerThumbnail = document.getElementById("playerThumbnail");

const loader = document.getElementById("loader");

const downloadForm = document.getElementById("downloadForm");

const urlInput = document.getElementById("urlInput");

const searchInput = document.getElementById("searchInput");

let allSongs = [];
let queue = [];
let currentIndex = -1;
let shuffle = false;
let repeat = false;

// ======================================
// LOAD SONGS
// ======================================

async function loadSongs() {
  const response = await fetch("/api/songs");

  const contentType = response.headers.get("content-type") || "";
  if (!response.ok || !contentType.includes("application/json")) {
    window.location.href = "/login";
    return;
  }

  const songs = await response.json();

  allSongs = songs;

  renderSongs(songs);
}

// ======================================
// RENDER SONGS
// ======================================

function renderSongs(songs) {
  songsContainer.innerHTML = "";

  songs.forEach((song) => {
    const div = document.createElement("div");

    div.className =
      "bg-zinc-900 border border-zinc-800 rounded-2xl p-3 md:p-4 flex items-center gap-3 md:gap-4 hover:bg-zinc-800 cursor-pointer transition";

    div.innerHTML = `
            <img
                src="${song.thumbnail_url}"
                class="w-16 h-16 md:w-20 md:h-20 rounded-xl object-cover shrink-0"
            >

            <div class="flex-1 min-w-0">
                <h2 class="font-semibold text-sm md:text-lg truncate">
                    ${song.title}
                </h2>

                <p class="text-zinc-400 text-xs md:text-base truncate">
                    ${song.uploader || "Unknown"}
                </p>
            </div>

            <button onclick="playNext(${JSON.stringify(song).replace(/"/g, "&quot;")})"
                    class="bg-yellow-600 px-3 py-1 rounded">
                Play Next
            </button>

            <button onclick="addToQueue(${JSON.stringify(song).replace(/"/g, "&quot;")})"
                    class="bg-green-600 px-3 py-1 rounded">
                Add
            </button>
        `;

    // div.onclick = () => {

    //     queue = allSongs
    //     currentIndex = queue.findIndex(s => s.id === song.id)

    //     playCurrent()
    // }

    div.onclick = () => {
      queue = [...allSongs];
      currentIndex = queue.findIndex((s) => s.id === song.id);

      playCurrent();
      renderQueue();
    };

    songsContainer.appendChild(div);
  });
}

// ======================================
// SEARCH
// ======================================

searchInput.addEventListener("input", () => {
  const value = searchInput.value.toLowerCase();

  const filtered = allSongs.filter((song) => {
    return (
      song.title.toLowerCase().includes(value) ||
      (song.uploader || "").toLowerCase().includes(value)
    );
  });

  renderSongs(filtered);
});

// ======================================
// DOWNLOAD
// ======================================

downloadForm.addEventListener("submit", async (e) => {
  e.preventDefault();

  const url = urlInput.value;

  if (!url) return;

  loader.classList.remove("hidden");

  const formData = new FormData();

  formData.append("url", url);

  const response = await fetch("/download", {
    method: "POST",
    body: formData,
  });

  if (response.redirected) {
    window.location.href = response.url;
    return;
  }

  urlInput.value = "";

  setTimeout(() => {
    loader.classList.add("hidden");
  }, 10000);
});

function playCurrent() {
  const song = queue[currentIndex];

  if (!song) return;

  player.src = `/api/stream/${song.id}`;
  player.play();

  playerTitle.innerText = song.title;
  playerUploader.innerText = song.uploader || "-";
  playerThumbnail.src = song.thumbnail_url;

  renderQueue();
}

function renderQueue() {
  const list = document.getElementById("queueList");

  list.innerHTML = "";

  queue.forEach((song, index) => {
    const isActive = index === currentIndex;

    const div = document.createElement("div");

    div.className =
      "p-2 rounded flex items-center justify-between cursor-move " +
      (isActive ? "bg-blue-600" : "bg-zinc-800");

    div.draggable = true;

    div.innerHTML = `
            <div class="truncate">
                ${isActive ? "▶ " : ""}${song.title}
            </div>

            <div class="flex gap-2">

                <button onclick="playNow(${index})">▶</button>
                <button onclick="removeFromQueue(${index})">✕</button>

            </div>
        `;

    // drag events
    div.ondragstart = (e) => {
      e.dataTransfer.setData("index", index);
    };

    div.ondragover = (e) => e.preventDefault();

    div.ondrop = (e) => {
      const from = e.dataTransfer.getData("index");
      const to = index;

      const moved = queue.splice(from, 1)[0];
      queue.splice(to, 0, moved);

      renderQueue();
    };

    list.appendChild(div);
  });
}

function playNow(index) {
  currentIndex = index;
  playCurrent();
}

function removeFromQueue(index) {
  queue.splice(index, 1);

  if (currentIndex >= queue.length) currentIndex = queue.length - 1;

  renderQueue();
}

function playNext(song) {
  if (currentIndex === -1) {
    queue = [song];
    currentIndex = 0;
  } else {
    queue.splice(currentIndex + 1, 0, song);
  }

  renderQueue();
}

function addToQueue(song) {
  queue.push(song);
  renderQueue();
}

function toggleShuffle() {
  shuffle = !shuffle;
}

function toggleRepeat() {
  repeat = !repeat;
}

function toggleQueue() {
  document.getElementById("queuePanel").classList.toggle("hidden");
}

player.addEventListener("ended", () => {
  if (repeat) {
    playCurrent();
    return;
  }

  if (shuffle) {
    currentIndex = Math.floor(Math.random() * queue.length);
    playCurrent();
    return;
  }

  if (currentIndex < queue.length - 1) {
    currentIndex++;
    playCurrent();
  }
});

// ======================================
// AUTO REFRESH
// ======================================

setInterval(loadSongs, 5000);

// ======================================
// INITIAL LOAD
// ======================================

loadSongs();

window.playNow = playNow;
window.removeFromQueue = removeFromQueue;
window.playNext = playNext;
window.addToQueue = addToQueue;

window.toggleShuffle = toggleShuffle;
window.toggleRepeat = toggleRepeat;
window.toggleQueue = toggleQueue;
