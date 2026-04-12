// Generated at request time by the BluePACS CD launcher (do not edit on disc).
window.config = {
  name: 'bluepacs-cd-launcher',
  routerBasename: null,
  extensions: [],
  modes: [],
  customizationService: {},
  showStudyList: true,
  maxNumberOfWebWorkers: 3,
  showWarningMessageForCrossOrigin: false,
  showCPUFallbackMessage: true,
  showLoadingIndicator: true,
  experimentalStudyBrowserSort: false,
  strictZSpacingForVolumeViewport: true,
  groupEnabledModesFirst: true,
  allowMultiSelectExport: false,
  maxNumRequests: {
    interaction: 100,
    thumbnail: 75,
    prefetch: 25,
  },
  defaultDataSourceName: 'bluepacs-local',
  dataSources: [
    {
      namespace: '@ohif/extension-default.dataSourcesModule.dicomweb',
      sourceName: 'bluepacs-local',
      configuration: {
        friendlyName: 'Images on this disc',
        name: 'bluepacs-local',
        wadoUriRoot: {{.DicomWebRoot}},
        qidoRoot: {{.DicomWebRoot}},
        wadoRoot: {{.DicomWebRoot}},
        qidoSupportsIncludeField: false,
        imageRendering: 'wadors',
        thumbnailRendering: 'wadors',
        // Disc server returns single-part application/dicom for /frames/N (not multipart/related).
        staticWado: true,
        singlepart: 'image,bulkdata,video',
        enableStudyLazyLoad: true,
        supportsFuzzyMatching: false,
        supportsWildcard: false,
        omitQuotationForMultipartRequest: true,
        bulkDataURI: {
          enabled: false,
        },
      },
    },
  ],
};
