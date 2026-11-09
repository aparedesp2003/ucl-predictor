import { CARD_ALT, CARD_SIZE, renderCard } from "./_og/card";

export const alt = CARD_ALT;
export const size = CARD_SIZE;
export const contentType = "image/png";

export default function Image() {
  return renderCard();
}
