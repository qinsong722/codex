import "./styles.css";
import { initGame } from "./game/ui";

const root = document.querySelector("#app");

if (root) {
  initGame(root);
}
