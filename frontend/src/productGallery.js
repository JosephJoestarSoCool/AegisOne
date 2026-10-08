/**
 * Brand product-art manifest for the Budget Optimizer.
 *
 * Keys are the application's company ids (the same ids the global brand switcher uses). Each brand maps ONLY to its own
 * folder under /public/products, so images can never cross brands. Order is fixed (01, 02, ...): the rotation is identical
 * on every load. `w`/`h` are the files' pixel sizes; they pick the fit (cover vs contained-on-blur) without waiting for load.
 *
 * These are supplied brand photographs used as visual context. They are NOT matched to catalog SKUs: the photos do not
 * identify a specific catalog product with confidence, so no product names are shown, only neutral "product archive" metadata.
 */
const set = (folder, files) => files.map(([file, w, h], i) => ({ src: `/products/${folder}/${file}`, index: i + 1, w, h }))

export const GALLERY = {
  nike: { folder: 'nike', images: set('nike', [['01.avif', 828, 1240], ['02.jpg', 3840, 2558], ['03.avif', 3840, 2561], ['04.avif', 1536, 1536], ['05.jpeg', 554, 554]]) },
  samsung: { folder: 'samsung', images: set('samsung', [['01.jpeg', 183, 275], ['02.jpeg', 335, 597], ['03.jpg', 736, 1308], ['04.jpg', 800, 1644]]) },
  lenovo: { folder: 'lenovo', images: set('lenovo', [['01.jpeg', 335, 597], ['02.jpeg', 678, 452], ['03.jpg', 1200, 675]]) },
  lv: { folder: 'louis-vuitton', images: set('louis-vuitton', [['01.jpeg', 639, 480], ['02.jpg', 500, 789], ['03.jpg', 1240, 840], ['04.jpeg', 350, 196]]) },
  supreme: { folder: 'supreme', images: set('supreme', [['01.jpeg', 399, 501], ['02.jpeg', 739, 415], ['03.jpeg', 387, 516], ['04.jpeg', 679, 452]]) },
}

export const galleryFor = (companyId) => GALLERY[companyId]?.images ?? []
