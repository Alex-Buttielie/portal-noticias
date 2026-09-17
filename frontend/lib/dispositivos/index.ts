// Barril do módulo de dispositivos: importa daqui.
// Uso:
//   import { DeviceProvider, useDispositivo } from "@/lib/dispositivos";
//   import { GradeAdaptativa } from "@/components/dispositivos/GradeAdaptativa";
//   import { NavegacaoAdaptativa } from "@/components/dispositivos/NavegacaoAdaptativa";

export * from "./tipos";
export * from "./detectar";
export { DeviceProvider, useDispositivo, useClasseDispositivo } from "./DeviceProvider";
