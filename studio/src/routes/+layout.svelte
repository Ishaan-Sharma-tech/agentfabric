<script lang="ts">
  import "../app.css";
  let { children } = $props();
</script>

<div class="studio-app">
  {@render children()}
</div>
