/// <reference path="../pb_data/types.d.ts" />

// Creates the public "waitlist" collection used by the landing page form.
// Runs automatically on `pocketbase serve`. (PocketBase v0.23+ JSVM API)
migrate((app) => {
  const collection = new Collection({
    type: "base",
    name: "waitlist",
    // Allow anonymous create (the public form); everything else admin-only so
    // the list isn't readable without the dashboard.
    listRule: null,
    viewRule: null,
    createRule: "",      // "" = anyone may create a record
    updateRule: null,
    deleteRule: null,
    fields: [
      { name: "email",  type: "email", required: true },
      { name: "volume", type: "text",  required: false, max: 120 },
      { name: "locale", type: "text",  required: false, max: 8 },
      { name: "source", type: "text",  required: false, max: 120 },
      { name: "created", type: "autodate", onCreate: true, onUpdate: false },
    ],
    indexes: [
      "CREATE UNIQUE INDEX idx_waitlist_email ON waitlist (email)",
    ],
  });

  app.save(collection);
}, (app) => {
  const collection = app.findCollectionByNameOrId("waitlist");
  app.delete(collection);
});
