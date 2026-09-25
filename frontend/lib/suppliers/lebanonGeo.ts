

export type LebanonMapPlace = {
  id: string;
  label: string;
  lat: number;
  lng: number;
  aliases: string[];
};

export const LEBANON_MAP_PLACES: LebanonMapPlace[] = [
  {
    id: "Tripoli",
    label: "Tripoli",
    lat: 34.434,
    lng: 35.844,
    aliases: ["tripoli", "north", "liban-nord", "akkar"],
  },
  {
    id: "Beirut",
    label: "Beirut",
    lat: 33.893,
    lng: 35.502,
    aliases: ["beirut", "beyrouth", "hamra", "raouche"],
  },
  {
    id: "Mkalles",
    label: "Mkalles",
    lat: 33.868,
    lng: 35.564,
    aliases: ["mkalles", "mount lebanon", "mont-liban", "aley", "baabda", "jounieh"],
  },
  {
    id: "Zahle",
    label: "Zahle",
    lat: 33.847,
    lng: 35.902,
    aliases: ["zahle", "zahlé", "bekaa", "beqaa", "béqaa"],
  },
  {
    id: "Baalbek",
    label: "Baalbek",
    lat: 34.006,
    lng: 36.218,
    aliases: ["baalbek", "baalbek-hermel", "hermel"],
  },
  {
    id: "Saida",
    label: "Saida",
    lat: 33.558,
    lng: 35.371,
    aliases: ["saida", "sidon", "south"],
  },
  {
    id: "Nabatieh",
    label: "Nabatieh",
    lat: 33.379,
    lng: 35.484,
    aliases: ["nabatieh", "nabatiye", "nabatîyé"],
  },
  {
    id: "Tyre",
    label: "Tyre",
    lat: 33.273,
    lng: 35.194,
    aliases: ["tyre", "sour", "sur"],
  },
];

export const LEBANON_VIEW = {
  center: [33.85, 35.7] as [number, number],
  zoom: 8,
  minZoom: 7,
  maxZoom: 12,
};
